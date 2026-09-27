terraform {
  backend "azurerm" {
    resource_group_name  = "rg-tfstate-staging"
    storage_account_name = "stztplatformstaging"
    container_name       = "tfstate"
    key                  = "zero-trust-platform/staging.tfstate"
  }
}
