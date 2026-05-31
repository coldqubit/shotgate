# qforge Terraform module — quantum workflow as code

Declare a quantum CI/CD quality gate as a Terraform resource. The module runs a
qforge workflow inside a container and (optionally) fails `terraform apply` when the
statistical assertions don't hold — making quantum validation a versioned, planned
part of your infrastructure.

> **Design choice.** We deliberately ship a *module that orchestrates the qforge
> container* rather than a bespoke Go provider. It needs no compilation, no plugin
> registry, and keeps the single source of truth (the validation logic) in one place.
> A native provider can come later (see [ADR-0003](../../docs/adr/0003-container-and-vm-isolation.md));
> the workflow contract stays identical.

## Usage

```hcl
module "bell_state_gate" {
  source = "github.com/your-org/qforge//infra/terraform"

  project_dir = abspath(path.root)               # dir mounted into the container
  workflow    = "examples/bell-state/workflow.yaml"
  image       = "qforge:dev"
  backend     = "local-aer"
  shots       = 8192
}
```

Run a real QPU by passing a token (kept out of state via `sensitive`):

```hcl
module "qpu_gate" {
  source   = "github.com/your-org/qforge//infra/terraform"
  workflow = "workflows/vqe.yaml"
  backend  = "ibm"
  env      = { QFORGE_IBM_TOKEN = var.ibm_token }
}
```

## Inputs

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `workflow` | string | — | Workflow YAML path, relative to `project_dir`. |
| `project_dir` | string | `"."` | Directory mounted into the container. |
| `image` | string | `"qforge:dev"` | qforge image to run. |
| `backend` | string | `"local-aer"` | `local-aer` \| `ibm` \| `braket`. |
| `shots` | number | `4096` | Shot-count override. |
| `report_dir` | string | `"qforge-reports"` | Where reports are written (under `project_dir`). |
| `env` | map(string) | `{}` | Env vars for the container (e.g. tokens). Sensitive. |
| `fail_on_assertion_error` | bool | `true` | Fail `apply` when assertions fail. |

## Outputs

| Name | Description |
| --- | --- |
| `report_xml_path` | Absolute path to the JUnit report. |
| `report_json_path` | Absolute path to the JSON report. |
| `execution_id` | ID of the underlying execution resource. |

## Run it without installing Terraform

```bash
make tf-plan   # runs hashicorp/terraform in a container against examples/basic
```
