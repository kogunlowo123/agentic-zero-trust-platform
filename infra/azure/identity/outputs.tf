output "policy_enforcer_client_id" {
  description = "Client ID of the policy-enforcer agent managed identity"
  value       = azurerm_user_assigned_identity.policy_enforcer_agent.client_id
}

output "policy_enforcer_object_id" {
  description = "Object ID of the policy-enforcer agent managed identity"
  value       = azurerm_user_assigned_identity.policy_enforcer_agent.principal_id
}

output "policy_enforcer_principal_id" {
  description = "Principal ID of the policy-enforcer agent managed identity"
  value       = azurerm_user_assigned_identity.policy_enforcer_agent.principal_id
}

output "posture_assessor_client_id" {
  description = "Client ID of the posture-assessor agent managed identity"
  value       = azurerm_user_assigned_identity.posture_assessor_agent.client_id
}

output "posture_assessor_object_id" {
  description = "Object ID of the posture-assessor agent managed identity"
  value       = azurerm_user_assigned_identity.posture_assessor_agent.principal_id
}

output "posture_assessor_principal_id" {
  description = "Principal ID of the posture-assessor agent managed identity"
  value       = azurerm_user_assigned_identity.posture_assessor_agent.principal_id
}

output "access_reviewer_client_id" {
  description = "Client ID of the access-reviewer agent managed identity"
  value       = azurerm_user_assigned_identity.access_reviewer_agent.client_id
}

output "access_reviewer_object_id" {
  description = "Object ID of the access-reviewer agent managed identity"
  value       = azurerm_user_assigned_identity.access_reviewer_agent.principal_id
}

output "access_reviewer_principal_id" {
  description = "Principal ID of the access-reviewer agent managed identity"
  value       = azurerm_user_assigned_identity.access_reviewer_agent.principal_id
}

output "workload_identity_annotations" {
  description = "Kubernetes service account annotations for each agent identity — annotate each ServiceAccount with the matching map"
  value = {
    policy_enforcer_agent = {
      "azure.workload.identity/client-id" = azurerm_user_assigned_identity.policy_enforcer_agent.client_id
    }
    posture_assessor_agent = {
      "azure.workload.identity/client-id" = azurerm_user_assigned_identity.posture_assessor_agent.client_id
    }
    access_reviewer_agent = {
      "azure.workload.identity/client-id" = azurerm_user_assigned_identity.access_reviewer_agent.client_id
    }
  }
}
