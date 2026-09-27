terraform {
  required_version = ">= 1.8"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
  }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy               = false
      recover_soft_deleted_key_vaults            = true
      purge_soft_deleted_secrets_on_destroy      = false
      recover_soft_deleted_secrets               = true
      purge_soft_deleted_certificates_on_destroy = false
      recover_soft_deleted_certificates          = true
    }
    resource_group {
      prevent_deletion_if_contains_resources = true
    }
  }
}

locals {
  common_tags = merge(var.tags, {
    environment = var.environment
    project     = "agentic-zero-trust-platform"
    managed_by  = "terraform"
  })
}

# ─── Monitoring (deployed first — AKS needs the workspace ID) ────────────────

module "monitor" {
  source = "../../../azure/monitor"

  location            = var.location
  resource_group_name = "rg-monitor-${var.environment}"
  workspace_name      = "law-zero-trust-${var.environment}"
  app_insights_name   = "appi-zero-trust-${var.environment}"
  alert_email_address = var.alert_email_address
  environment         = var.environment

  # Set aks_cluster_id after the first successful apply to activate CPU/memory
  # alerts. Leave empty on first deployment to avoid a module-level cycle
  # (monitor creates the workspace that AKS consumes).
  aks_cluster_id = var.aks_cluster_id

  tags = local.common_tags
}

# ─── Networking ───────────────────────────────────────────────────────────────

module "network" {
  source = "../../../azure/network"

  location            = var.location
  resource_group_name = "rg-network-${var.environment}"
  vnet_name           = "vnet-zero-trust-${var.environment}"
  environment         = var.environment
  tags                = local.common_tags
}

# ─── AKS Cluster ─────────────────────────────────────────────────────────────

module "aks" {
  source = "../../../azure/aks"

  location                   = var.location
  resource_group_name        = "rg-aks-${var.environment}"
  cluster_name               = var.cluster_name
  kubernetes_version         = var.kubernetes_version
  aks_subnet_id              = module.network.aks_subnet_id
  log_analytics_workspace_id = module.monitor.workspace_id
  acr_name                   = var.acr_name
  acr_replica_location       = var.acr_replica_location
  environment                = var.environment
  tags                       = local.common_tags
}

# ─── PostgreSQL Flexible Server ───────────────────────────────────────────────

module "postgres" {
  source = "../../../azure/postgres-flex"

  location            = var.location
  resource_group_name = "rg-postgres-${var.environment}"
  server_name         = "psql-zero-trust-${var.environment}"
  sku_name            = var.postgres_sku_name
  postgres_version    = var.postgres_version
  delegated_subnet_id = module.network.postgres_subnet_id
  private_dns_zone_id = module.network.private_dns_zone_id

  # The AKS kubelet identity is used as the PostgreSQL AAD administrator
  # so agent workloads can obtain connection tokens via Workload Identity.
  aks_workload_identity_object_id      = module.aks.kubelet_identity_object_id
  aks_workload_identity_principal_name = "aks-${var.cluster_name}-agentpool"

  environment = var.environment
  tags        = local.common_tags
}

# ─── Key Vault ───────────────────────────────────────────────────────────────

module "keyvault" {
  source = "../../../azure/keyvault"

  location            = var.location
  resource_group_name = "rg-keyvault-${var.environment}"
  key_vault_name      = var.key_vault_name
  private_endpoints_subnet_id = module.network.private_endpoints_subnet_id
  vnet_id             = module.network.vnet_id

  # Grant the kubelet identity access so node-level secret rotation works;
  # the identity module grants agent-level access to the per-agent identities.
  aks_workload_identity_principal_id = module.aks.kubelet_identity_object_id

  environment = var.environment
  tags        = local.common_tags
}

# ─── Service Bus ─────────────────────────────────────────────────────────────

module "servicebus" {
  source = "../../../azure/servicebus"

  location            = var.location
  resource_group_name = "rg-servicebus-${var.environment}"
  namespace_name      = "sb-zero-trust-${var.environment}"
  private_endpoints_subnet_id = module.network.private_endpoints_subnet_id
  vnet_id             = module.network.vnet_id

  aks_identity_principal_id = module.aks.kubelet_identity_object_id

  environment = var.environment
  tags        = local.common_tags
}

# ─── AI Search ────────────────────────────────────────────────────────────────

module "ai_search" {
  source = "../../../azure/ai-search"

  location            = var.location
  resource_group_name = "rg-search-${var.environment}"
  search_service_name = var.search_service_name
  replica_count       = var.search_replica_count
  private_endpoints_subnet_id = module.network.private_endpoints_subnet_id
  vnet_id             = module.network.vnet_id

  aks_identity_principal_id = module.aks.kubelet_identity_object_id

  environment = var.environment
  tags        = local.common_tags
}

# ─── Agent Managed Identities ────────────────────────────────────────────────

module "identity" {
  source = "../../../azure/identity"

  location            = var.location
  resource_group_name = "rg-identity-${var.environment}"
  aks_oidc_issuer_url = module.aks.oidc_issuer_url
  key_vault_id        = module.keyvault.key_vault_id

  # Grant each agent identity access to Service Bus queues and AI Search index
  servicebus_namespace_id = module.servicebus.namespace_id
  search_service_id       = module.ai_search.search_service_id

  # Provide the full Azure OpenAI resource ID; set in terraform.tfvars.
  azure_openai_resource_id = var.azure_openai_resource_id

  kubernetes_namespace = var.kubernetes_namespace
  environment          = var.environment
  tags                 = local.common_tags
}
