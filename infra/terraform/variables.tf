variable "project_dir" {
  description = "Directory mounted into the qforge container (contains workflows and circuits)."
  type        = string
  default     = "."
}

variable "workflow" {
  description = "Path to the workflow YAML, relative to project_dir."
  type        = string
}

variable "image" {
  description = "qforge container image to execute."
  type        = string
  default     = "qforge:dev"
}

variable "backend" {
  description = "Backend provider override (local-aer | ibm | braket)."
  type        = string
  default     = "local-aer"

  validation {
    condition     = contains(["local-aer", "ibm", "braket"], var.backend)
    error_message = "backend must be one of: local-aer, ibm, braket."
  }
}

variable "shots" {
  description = "Shot-count override applied to every job."
  type        = number
  default     = 4096
}

variable "report_dir" {
  description = "Directory (relative to project_dir) where reports are written."
  type        = string
  default     = "qforge-reports"
}

variable "podman_bin" {
  description = "Container engine binary on the machine running terraform apply."
  type        = string
  default     = "podman"
}

variable "env" {
  description = "Environment variables passed to the container (e.g. QFORGE_IBM_TOKEN). Marked sensitive."
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "fail_on_assertion_error" {
  description = "If true, terraform apply fails when any quantum assertion fails."
  type        = bool
  default     = true
}
