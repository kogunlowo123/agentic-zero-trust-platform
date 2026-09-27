output "workspace_id" {
  description = "ID of the Log Analytics workspace"
  value       = azurerm_log_analytics_workspace.main.id
}

output "workspace_key" {
  description = "Primary shared key for the Log Analytics workspace"
  value       = azurerm_log_analytics_workspace.main.primary_shared_key
  sensitive   = true
}

output "workspace_name" {
  description = "Name of the Log Analytics workspace"
  value       = azurerm_log_analytics_workspace.main.name
}

output "app_insights_id" {
  description = "ID of the Application Insights instance"
  value       = azurerm_application_insights.main.id
}

output "app_insights_connection_string" {
  description = "Connection string for the Application Insights instance"
  value       = azurerm_application_insights.main.connection_string
  sensitive   = true
}

output "instrumentation_key" {
  description = "Instrumentation key for Application Insights (use connection string for new deployments)"
  value       = azurerm_application_insights.main.instrumentation_key
  sensitive   = true
}

output "resource_group_name" {
  description = "Name of the monitoring resource group"
  value       = azurerm_resource_group.monitor.name
}
