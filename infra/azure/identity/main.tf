terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
  }
}

resource "azurerm_resource_group" "identity" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

# ─── Agent Managed Identities ────────────────────────────────────────────────

resource "azurerm_user_assigned_identity" "policy_enforcer_agent" {
  name                = "id-policy-enforcer-${var.environment}"
  resource_group_name = azurerm_resource_group.identity.name
  location            = azurerm_resource_group.identity.location
  tags                = var.tags
}

resource "azurerm_user_assigned_identity" "posture_assessor_agent" {
  name                = "id-posture-assessor-${var.environment}"
  resource_group_name = azurerm_resource_group.identity.name
  location            = azurerm_resource_group.identity.location
  tags                = var.tags
}

resource "azurerm_user_assigned_identity" "access_reviewer_agent" {
  name                = "id-access-reviewer-${var.environment}"
  resource_group_name = azurerm_resource_group.identity.name
  location            = azurerm_resource_group.identity.location
  tags                = var.tags
}

# ─── Federated Identity Credentials (Kubernetes Workload Identity) ────────────

resource "azurerm_federated_identity_credential" "policy_enforcer_agent" {
  name                = "fic-policy-enforcer-${var.environment}"
  resource_group_name = azurerm_resource_group.identity.name
  parent_id           = azurerm_user_assigned_identity.policy_enforcer_agent.id
  issuer              = var.aks_oidc_issuer_url
  subject             = "system:serviceaccount:${var.kubernetes_namespace}:policy-enforcer-agent"
  audience            = ["api://AzureADTokenExchange"]
}

resource "azurerm_federated_identity_credential" "posture_assessor_agent" {
  name                = "fic-posture-assessor-${var.environment}"
  resource_group_name = azurerm_resource_group.identity.name
  parent_id           = azurerm_user_assigned_identity.posture_assessor_agent.id
  issuer              = var.aks_oidc_issuer_url
  subject             = "system:serviceaccount:${var.kubernetes_namespace}:posture-assessor-agent"
  audience            = ["api://AzureADTokenExchange"]
}

resource "azurerm_federated_identity_credential" "access_reviewer_agent" {
  name                = "fic-access-reviewer-${var.environment}"
  resource_group_name = azurerm_resource_group.identity.name
  parent_id           = azurerm_user_assigned_identity.access_reviewer_agent.id
  issuer              = var.aks_oidc_issuer_url
  subject             = "system:serviceaccount:${var.kubernetes_namespace}:access-reviewer-agent"
  audience            = ["api://AzureADTokenExchange"]
}

# ─── Azure OpenAI Role Assignments ───────────────────────────────────────────

resource "azurerm_role_assignment" "policy_enforcer_openai" {
  scope                = var.azure_openai_resource_id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.policy_enforcer_agent.principal_id
}

resource "azurerm_role_assignment" "posture_assessor_openai" {
  scope                = var.azure_openai_resource_id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.posture_assessor_agent.principal_id
}

resource "azurerm_role_assignment" "access_reviewer_openai" {
  scope                = var.azure_openai_resource_id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.access_reviewer_agent.principal_id
}

# ─── Key Vault Secrets User Role Assignments ──────────────────────────────────

resource "azurerm_role_assignment" "policy_enforcer_kv" {
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.policy_enforcer_agent.principal_id
}

resource "azurerm_role_assignment" "posture_assessor_kv" {
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.posture_assessor_agent.principal_id
}

resource "azurerm_role_assignment" "access_reviewer_kv" {
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.access_reviewer_agent.principal_id
}

# ─── Service Bus Role Assignments ─────────────────────────────────────────────

resource "azurerm_role_assignment" "policy_enforcer_sb_sender" {
  scope                = var.servicebus_namespace_id
  role_definition_name = "Azure Service Bus Data Sender"
  principal_id         = azurerm_user_assigned_identity.policy_enforcer_agent.principal_id
}

resource "azurerm_role_assignment" "policy_enforcer_sb_receiver" {
  scope                = var.servicebus_namespace_id
  role_definition_name = "Azure Service Bus Data Receiver"
  principal_id         = azurerm_user_assigned_identity.policy_enforcer_agent.principal_id
}

resource "azurerm_role_assignment" "posture_assessor_sb_sender" {
  scope                = var.servicebus_namespace_id
  role_definition_name = "Azure Service Bus Data Sender"
  principal_id         = azurerm_user_assigned_identity.posture_assessor_agent.principal_id
}

resource "azurerm_role_assignment" "posture_assessor_sb_receiver" {
  scope                = var.servicebus_namespace_id
  role_definition_name = "Azure Service Bus Data Receiver"
  principal_id         = azurerm_user_assigned_identity.posture_assessor_agent.principal_id
}

resource "azurerm_role_assignment" "access_reviewer_sb_sender" {
  scope                = var.servicebus_namespace_id
  role_definition_name = "Azure Service Bus Data Sender"
  principal_id         = azurerm_user_assigned_identity.access_reviewer_agent.principal_id
}

resource "azurerm_role_assignment" "access_reviewer_sb_receiver" {
  scope                = var.servicebus_namespace_id
  role_definition_name = "Azure Service Bus Data Receiver"
  principal_id         = azurerm_user_assigned_identity.access_reviewer_agent.principal_id
}

# ─── AI Search Role Assignments ────────────────────────────────────────────────

resource "azurerm_role_assignment" "policy_enforcer_search" {
  scope                = var.search_service_id
  role_definition_name = "Search Index Data Contributor"
  principal_id         = azurerm_user_assigned_identity.policy_enforcer_agent.principal_id
}

resource "azurerm_role_assignment" "posture_assessor_search" {
  scope                = var.search_service_id
  role_definition_name = "Search Index Data Contributor"
  principal_id         = azurerm_user_assigned_identity.posture_assessor_agent.principal_id
}

resource "azurerm_role_assignment" "access_reviewer_search" {
  scope                = var.search_service_id
  role_definition_name = "Search Index Data Contributor"
  principal_id         = azurerm_user_assigned_identity.access_reviewer_agent.principal_id
}
