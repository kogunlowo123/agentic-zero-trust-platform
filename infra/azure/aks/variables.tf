variable "location" {
  description = "Azure region for AKS resources"
  type        = string
  default     = "eastus2"
}

variable "resource_group_name" {
  description = "Name of the resource group for AKS resources"
  type        = string
}

variable "cluster_name" {
  description = "Name of the AKS cluster"
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version for the AKS cluster"
  type        = string
  default     = "1.29"
}

variable "aks_subnet_id" {
  description = "ID of the subnet where AKS nodes are deployed"
  type        = string
}

variable "log_analytics_workspace_id" {
  description = "ID of the Log Analytics workspace for AKS monitoring and Defender"
  type        = string
}

variable "acr_name" {
  description = "Name of the Azure Container Registry (must be globally unique, alphanumeric only)"
  type        = string
}

variable "acr_replica_location" {
  description = "Azure region for ACR geo-replication"
  type        = string
  default     = "westus2"
}

variable "node_count" {
  description = "Initial node count (used only when auto-scaling is disabled)"
  type        = number
  default     = 2
}

variable "vm_size" {
  description = "VM size for the AKS default system node pool"
  type        = string
  default     = "Standard_D4s_v3"
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
