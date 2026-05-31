output "workflow" {
  description = "Workflow that this module gates on."
  value       = var.workflow
}

output "report_xml_path" {
  description = "Absolute path to the JUnit report produced on apply."
  value       = "${local.project_dir_abs}/${local.report_xml}"
}

output "report_json_path" {
  description = "Absolute path to the JSON report produced on apply."
  value       = "${local.project_dir_abs}/${local.report_json}"
}

output "execution_id" {
  description = "Identifier of the underlying execution resource."
  value       = terraform_data.quantum_workflow.id
}
