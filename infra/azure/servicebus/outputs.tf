output "namespace_id" {
  description = "ID of the Service Bus namespace"
  value       = azurerm_servicebus_namespace.main.id
}

output "namespace_name" {
  description = "Name of the Service Bus namespace"
  value       = azurerm_servicebus_namespace.main.name
}

output "namespace_endpoint" {
  description = "Service Bus namespace endpoint"
  value       = azurerm_servicebus_namespace.main.endpoint
}

output "policy_violations_queue_id" {
  description = "ID of the policy-violations queue"
  value       = azurerm_servicebus_queue.policy_violations.id
}

output "access_requests_queue_id" {
  description = "ID of the access-requests queue"
  value       = azurerm_servicebus_queue.access_requests.id
}

output "posture_events_queue_id" {
  description = "ID of the posture-events queue"
  value       = azurerm_servicebus_queue.posture_events.id
}

output "resource_group_name" {
  description = "Name of the Service Bus resource group"
  value       = azurerm_resource_group.servicebus.name
}
