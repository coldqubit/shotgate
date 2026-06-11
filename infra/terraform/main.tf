# shotgate IaC module: declare a quantum CI workflow as code.
#
# This expresses "run quantum workflow X, on backend Y, with Z shots, and gate on
# the statistical result" as a Terraform resource. Execution is delegated to the
# shotgate container, so the only host dependency is a container engine (Podman).
#
# The run re-executes whenever the workflow file, image, backend, or shot count
# changes (tracked via triggers_replace), making quantum validation a first-class,
# versioned part of your infrastructure plan.

locals {
  project_dir_abs = abspath(var.project_dir)
  report_xml      = "${var.report_dir}/report.xml"
  report_json     = "${var.report_dir}/report.json"

  # Render `-e KEY=VALUE` flags for any environment variables (e.g. cloud tokens).
  env_flags = join(" ", [for k, v in var.env : "-e ${k}=${v}"])
}

resource "terraform_data" "quantum_workflow" {
  # Re-run the gate when any input that affects the result changes.
  triggers_replace = {
    workflow_sha = filesha256("${local.project_dir_abs}/${var.workflow}")
    image        = var.image
    backend      = var.backend
    shots        = var.shots
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    environment = {
      SHOTGATE_FAIL = var.fail_on_assertion_error ? "1" : "0"
    }
    command = <<-EOT
      set -euo pipefail
      mkdir -p "${local.project_dir_abs}/${var.report_dir}"

      # Map the invoking user through the container userns so the non-root image
      # can write reports back to the bind mount, owned by the caller.
      USERMAP="--userns=keep-id --user $(id -u):$(id -g)"

      set +e
      ${var.podman_bin} run --rm $USERMAP \
        -v "${local.project_dir_abs}:/work:Z" -w /work \
        ${local.env_flags} \
        "${var.image}" run "${var.workflow}" \
          --backend "${var.backend}" \
          --shots "${var.shots}" \
          --junit "/work/${local.report_xml}" \
          --json  "/work/${local.report_json}"
      rc=$?
      set -e

      echo "shotgate exit code: $rc"
      if [ "$SHOTGATE_FAIL" = "1" ] && [ "$rc" -ne 0 ]; then
        echo "quantum assertions failed; failing terraform apply" >&2
        exit "$rc"
      fi
    EOT
  }
}
