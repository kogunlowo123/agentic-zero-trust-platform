variable "environment" {
  description = "Environment name"
  type        = string
  default     = "staging"
}

variable "location" {
  description = "Primary Azure region"
  type        = string
  default     = "eastus2"
}

variable "cluster_name" {
  description = "AKS cluster name"
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version for the AKS cluster"
  type        = string
  default     = "1.29"
}

variable "acr_name" {
  description = "Azure Container Registry name (globally unique, alphanumeric only)"
  type        = string
}

variable "acr_replica_location" {
  description = "Secondary Azure region for ACR geo-replication"
  type        = string
  default     = "westus2"
}

variable "key_vault_name" {
  description = "Key Vault name (globally unique)"
  type        = string
}

variable "postgres_sku_name" {
  description = "SKU for the PostgreSQL Flexible Server"
  type        = string
  default     = "GP_Standard_D4s_v3"
}

variable "postgres_version" {
  description = "PostgreSQL major version"
  type        = string
  default     = "16"
}

variable "search_service_name" {
  description = "Azure AI Search service name (globally unique)"
  type        = string
}

variable "search_replica_count" {
  description = "Number of replicas for the AI Search service"
  type        = number
  default     = 2
}

variable "kubernetes_namespace" {
  description = "Kubernetes namespace for agent workloads"
  type        = string
  default     = "agentic-zero-trust"
}

variable "azure_openai_resource_id" {
  description = "Full resource ID of the Azure OpenAI resource"
  type        = string
}

variable "alert_email_address" {
  description = "Email address for critical platform alerts"
  type        = string
}

variable "aks_cluster_id" {
  description = "AKS cluster ID for monitoring alerts — leave empty on initial deployment"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional tags to merge with common tags"
  type        = map(string)
  default     = {}
}
