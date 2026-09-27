variable "location" {
  description = "Azure region for monitoring resources"
  type        = string
  default     = "eastus2"
}

variable "resource_group_name" {
  description = "Name of the resource group for monitoring resources"
  type        = string
}

variable "workspace_name" {
  description = "Name of the Log Analytics workspace"
  type        = string
}

variable "app_insights_name" {
  description = "Name of the Application Insights instance"
  type        = string
}

variable "aks_cluster_id" {
  description = "ID of the AKS cluster to monitor — leave empty on initial deployment to avoid circular dependency; set after AKS is provisioned to activate CPU and memory alerts"
  type        = string
  default     = ""
}

variable "alert_email_address" {
  description = "Email address that receives critical platform alerts"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
