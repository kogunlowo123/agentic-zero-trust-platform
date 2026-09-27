output "server_id" {
  description = "ID of the PostgreSQL Flexible Server"
  value       = azurerm_postgresql_flexible_server.main.id
}

output "server_fqdn" {
  description = "Fully qualified domain name of the PostgreSQL Flexible Server"
  value       = azurerm_postgresql_flexible_server.main.fqdn
}

output "database_name" {
  description = "Name of the platform database"
  value       = azurerm_postgresql_flexible_server_database.platform.name
}

output "connection_string" {
  description = "PostgreSQL connection string in postgresql://user@server/db format (password-less; authenticate with an AAD token)"
  value       = "postgresql://${var.aks_workload_identity_principal_name}@${azurerm_postgresql_flexible_server.main.fqdn}/${azurerm_postgresql_flexible_server_database.platform.name}"
  sensitive   = false
}

output "resource_group_name" {
  description = "Name of the PostgreSQL resource group"
  value       = azurerm_resource_group.postgres.name
}
