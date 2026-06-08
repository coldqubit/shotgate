// Reference declarative Jenkins pipeline for gating on a shotgate quantum workflow.
//
// PULLS the published image and runs the gate via the container, then publishes the
// JUnit report. A failed statistical assertion makes shotgate exit 1, which fails the
// stage (and, via junit, marks the build UNSTABLE/FAILED). Exit-code contract:
// 0 = pass, 1 = a gate failed, 2 = bad config. The contract matches GitHub/GitLab/Jenkins.
//
// Requires a container engine (podman or docker) on the agent.

pipeline {
    agent any

    environment {
        SHOTGATE_IMAGE = 'ghcr.io/coldqubit/shotgate:latest'
        WORKFLOW       = 'examples/bell-state/workflow.yaml'
    }

    stages {
        stage('Quantum gate') {
            steps {
                sh '''
                    set -e
                    podman run --rm \
                      --userns=keep-id --user "$(id -u):$(id -g)" \
                      -v "$PWD:/work:Z" -w /work \
                      "$SHOTGATE_IMAGE" \
                      run "$WORKFLOW" --junit report.xml --json report.json
                '''
            }
        }
    }

    post {
        always {
            // Surface assertion-level pass/fail in the Jenkins test UI.
            junit testResults: 'report.xml', allowEmptyResults: false
            archiveArtifacts artifacts: 'report.json', allowEmptyArchive: true
        }
    }
}

// Cloud/QPU variant: use 'ghcr.io/coldqubit/shotgate:latest-ibm', pass a token via a
// Jenkins credential, and run the noise-tolerant workflow:
//
//   withCredentials([string(credentialsId: 'shotgate-ibm-token', variable: 'SHOTGATE_IBM_TOKEN')]) {
//     sh '''
//       podman run --rm -e SHOTGATE_IBM_TOKEN -v "$PWD:/work:Z" -w /work \
//         ghcr.io/coldqubit/shotgate:latest-ibm \
//         run examples/bell-state-hardware/workflow.yaml --backend ibm --junit report.xml
//     '''
//   }

// Pip alternative (no image pull): install the package and gate with the CLI or the
// pytest plugin instead of pulling the container image.
//
//   sh '''
//     pip install "shotgate[aer]"
//     shotgate run "$WORKFLOW" --junit report.xml          # CLI path
//     pytest --shotgate "$WORKFLOW" --junitxml=report.xml  # pytest plugin path
//   '''
