terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
  }
}

resource "azurerm_resource_group" "monitor" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

resource "azurerm_log_analytics_workspace" "main" {
  name                = var.workspace_name
  location            = azurerm_resource_group.monitor.location
  resource_group_name = azurerm_resource_group.monitor.name
  sku                 = "PerGB2018"
  retention_in_days   = 90
  tags                = var.tags
}

resource "azurerm_application_insights" "main" {
  name                = var.app_insights_name
  location            = azurerm_resource_group.monitor.location
  resource_group_name = azurerm_resource_group.monitor.name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"
  tags                = var.tags
}

resource "azurerm_monitor_action_group" "critical" {
  name                = "ag-critical-${var.environment}"
  resource_group_name = azurerm_resource_group.monitor.name
  short_name          = "critical"

  email_receiver {
    name                    = "platform-admin"
    email_address           = var.alert_email_address
    use_common_alert_schema = true
  }

  tags = var.tags
}

# AKS CPU alert — enabled only when aks_cluster_id is provided.
# On initial deploy, leave aks_cluster_id = "" (workspace is created first,
# then AKS is deployed using the workspace ID). Set aks_cluster_id after first
# deployment to activate these alerts.
resource "azurerm_monitor_metric_alert" "aks_cpu" {
  count = var.aks_cluster_id != "" ? 1 : 0

  name                = "alert-aks-cpu-${var.environment}"
  resource_group_name = azurerm_resource_group.monitor.name
  scopes              = [var.aks_cluster_id]
  description         = "AKS cluster average CPU utilisation exceeded 80%"
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"
  auto_mitigate       = true

  criteria {
    metric_namespace = "Microsoft.ContainerService/managedClusters"
    metric_name      = "node_cpu_usage_percentage"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  action {
    action_group_id = azurerm_monitor_action_group.critical.id
  }

  tags = var.tags
}

resource "azurerm_monitor_metric_alert" "aks_memory" {
  count = var.aks_cluster_id != "" ? 1 : 0

  name                = "alert-aks-memory-${var.environment}"
  resource_group_name = azurerm_resource_group.monitor.name
  scopes              = [var.aks_cluster_id]
  description         = "AKS cluster average working-set memory utilisation exceeded 85%"
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"
  auto_mitigate       = true

  criteria {
    metric_namespace = "Microsoft.ContainerService/managedClusters"
    metric_name      = "node_memory_working_set_percentage"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 85
  }

  action {
    action_group_id = azurerm_monitor_action_group.critical.id
  }

  tags = var.tags
}
