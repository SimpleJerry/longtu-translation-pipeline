// Declarative pipeline — longtu translation service (ADR-0035)
// Stages: Checkout → Test → Build → Deploy → HealthCheck
//
// Rollback strategy: single-host blue-green (validate-then-switch).
// New container starts on staging port 8001 with name ${CONTAINER}-new.
// Old container keeps serving on port 8000 throughout the health check.
// On success: old container stopped, new container restarted as official on port 8000.
// On failure: new container removed; old container continues serving uninterrupted.

pipeline {
    agent any

    environment {
        IMAGE_NAME   = 'longtu-translation-service'
        IMAGE_TAG    = "${env.BUILD_NUMBER}"
        CONTAINER    = 'longtu-translation'
        // Host directory containing run_manifest.json + checkpoint-48000/
        // Matches the mount protocol: -v MODEL_DIR:/models:ro  (ADR-0035 sec 5)
        MODEL_DIR    = '/opt/longtu/models'
        HOST_PORT    = '8000'
        STAGING_PORT = '8001'
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Test') {
            // Isolated docker agent prevents pip pollution of the Jenkins node environment.
            // reuseNode true mounts the same workspace so checked-out code is available.
            agent {
                docker {
                    image 'python:3.12-slim'
                    reuseNode true
                }
            }
            steps {
                // CPU-only torch mirrors the GitHub Actions CI setup (ci.yml).
                // GPU is not required for the contract test suite.
                sh 'pip install torch==2.12.0 --index-url https://download.pytorch.org/whl/cpu'
                sh 'pip install -r requirements.txt -r requirements-dev.txt'
                sh 'OMP_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false pytest --timeout=120'
            }
        }

        stage('Build') {
            steps {
                sh "docker build -t ${IMAGE_NAME}:${IMAGE_TAG} ."
            }
        }

        stage('Deploy') {
            steps {
                sh """
                    # Remove any leftover staging container from a previous failed build
                    docker rm -f ${CONTAINER}-new || true

                    # Start new container on staging port — old container keeps serving on ${HOST_PORT}
                    docker run -d \\
                        --name ${CONTAINER}-new \\
                        --gpus all \\
                        -v ${MODEL_DIR}:/models:ro \\
                        -p ${STAGING_PORT}:8000 \\
                        --restart unless-stopped \\
                        ${IMAGE_NAME}:${IMAGE_TAG}
                """
            }
        }

        stage('HealthCheck') {
            steps {
                sh """
                    echo 'Waiting for staging container to become healthy (up to 120 s)...'
                    ok=0
                    for i in \$(seq 1 24); do
                        if curl -sf http://localhost:${STAGING_PORT}/health > /dev/null 2>&1; then
                            echo "Health check passed on attempt \$i"
                            ok=1
                            break
                        fi
                        echo "Attempt \$i/24: not ready, sleeping 5 s..."
                        sleep 5
                    done
                    if [ \$ok -eq 0 ]; then
                        echo 'Staging container did not become healthy within 120 s'
                        exit 1
                    fi

                    # Smoke test: single item with a game term (ADR-0035 sec 6 / ADR-0034)
                    curl -sf -X POST http://localhost:${STAGING_PORT}/translate \\
                        -H 'Content-Type: application/json' \\
                        -d '{"items":[{"id":"smoke","text":"攻击力增加50%"}]}' \\
                        -o /tmp/smoke_result.json

                    python3 -c "
import json
with open('/tmp/smoke_result.json', encoding='utf-8') as f:
    data = json.load(f)
t = data['results'][0]['translation']
assert t and len(t.strip()) > 0, f'Empty translation: {t!r}'
print('Smoke PASSED:', t)
"

                    # Atomic switch: stop old, re-launch new as official container on port ${HOST_PORT}
                    echo 'Health check and smoke passed — switching to new container on port ${HOST_PORT}'
                    docker stop ${CONTAINER} || true
                    docker rm   ${CONTAINER} || true
                    docker stop  ${CONTAINER}-new
                    docker rm    ${CONTAINER}-new
                    docker run -d \\
                        --name ${CONTAINER} \\
                        --gpus all \\
                        -v ${MODEL_DIR}:/models:ro \\
                        -p ${HOST_PORT}:8000 \\
                        --restart unless-stopped \\
                        ${IMAGE_NAME}:${IMAGE_TAG}
                """
            }
            post {
                failure {
                    sh """
                        echo 'HealthCheck failed — removing staging container; old container continues serving on port ${HOST_PORT}'
                        docker rm -f ${CONTAINER}-new || true
                    """
                }
            }
        }
    }

    post {
        always {
            // Remove dangling images to reclaim disk space after each build
            sh "docker image prune -f --filter 'dangling=true'"
        }
    }
}
