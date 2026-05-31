# Example: gate a Terraform apply on a quantum workflow's statistical assertions.
#
#   terraform init
#   terraform apply        # builds nothing classical — it validates a Bell state
#
# Requires the qforge image to exist locally (make build) and Podman on the host.

module "bell_state_gate" {
  source = "../.."

  # Repo root, four levels up from infra/terraform/examples/basic.
  project_dir = abspath("${path.module}/../../../..")
  workflow    = "examples/bell-state/workflow.yaml"

  image   = "qforge:dev"
  backend = "local-aer"
  shots   = 8192
}

output "bell_report" {
  value = module.bell_state_gate.report_json_path
}
