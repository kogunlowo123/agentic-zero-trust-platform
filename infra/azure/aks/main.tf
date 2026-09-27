terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
  }
}

resource "azurerm_resource_group" "aks" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

resource "azurerm_user_assigned_identity" "aks" {
  name                = "id-aks-${var.cluster_name}"
  resource_group_name = azurerm_resource_group.aks.name
  location            = azurerm_resource_group.aks.location
  tags                = var.tags
}

resource "azurerm_container_registry" "acr" {
  name                = var.acr_name
  resource_group_name = azurerm_resource_group.aks.name
  location            = azurerm_resource_group.aks.location
  sku                 = "Premium"
  admin_enabled       = false

  georeplications {
    location                = var.acr_replica_location
    zone_redundancy_enabled = true
    tags                    = var.tags
  }

  tags = var.tags
}

resource "azurerm_kubernetes_cluster" "main" {
  name                    = var.cluster_name
  location                = azurerm_resource_group.aks.location
  resource_group_name     = azurerm_resource_group.aks.name
  kubernetes_version      = var.kubernetes_version
  dns_prefix              = "${var.cluster_name}-dns"
  private_cluster_enabled = true
  azure_policy_enabled    = true
  oidc_issuer_enabled     = true
  workload_identity_enabled = true

  default_node_pool {
    name                = "system"
    vm_size             = var.vm_size
    os_disk_type        = "Ephemeral"
    vnet_subnet_id      = var.aks_subnet_id
    enable_auto_scaling = true
    min_count           = 2
    max_count           = 5
    # node_count sets the initial node count; autoscaler manages it afterward.
    # Ignore drift in state to prevent Terraform from resetting the count on
    # every plan when the autoscaler has scaled the pool.
    node_count = var.node_count
    type       = "VirtualMachineScaleSets"

    node_labels = {
      "nodepool-type" = "system"
      "environment"   = var.environment
    }
  }

  lifecycle {
    ignore_changes = [
      default_node_pool[0].node_count,
    ]
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.aks.id]
  }

  network_profile {
    network_plugin    = "azure"
    network_policy    = "azure"
    service_cidr      = "10.100.0.0/16"
    dns_service_ip    = "10.100.0.10"
    load_balancer_sku = "standard"
  }

  microsoft_defender {
    log_analytics_workspace_id = var.log_analytics_workspace_id
  }

  key_vault_secrets_provider {
    secret_rotation_enabled = true
  }

  oms_agent {
    log_analytics_workspace_id = var.log_analytics_workspace_id
  }

  tags = var.tags
}

resource "azurerm_kubernetes_cluster_node_pool" "user" {
  name                  = "userpool"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.main.id
  vm_size               = "Standard_D4s_v3"
  vnet_subnet_id        = var.aks_subnet_id
  enable_auto_scaling   = true
  min_count             = 1
  max_count             = 10
  mode                  = "User"

  node_labels = {
    "nodepool-type" = "user"
    "workload"      = "application"
    "environment"   = var.environment
  }

  # No taints on the user pool; the system pool enforces separation
  # via the CriticalAddonsOnly=true:NoSchedule taint (applied automatically
  # by AKS to System-mode node pools).
  node_taints = []

  tags = var.tags
}

# AcrPull is assigned to the kubelet identity (the identity that pulls images),
# not the control-plane user-assigned identity.
resource "azurerm_role_assignment" "acr_pull" {
  principal_id                     = azurerm_kubernetes_cluster.main.kubelet_identity[0].object_id
  role_definition_name             = "AcrPull"
  scope                            = azurerm_container_registry.acr.id
  skip_service_principal_aad_check = true
}
