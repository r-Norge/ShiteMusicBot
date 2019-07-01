pipeline {
    agent none
    environment {
        GIT_REPO = 'si0972/ShiteMusicBot'
        DOCKER_REPO = 'si0972/ci_test_musikkbot'
        TAG=""
        FLAKE_FILES = "bot.py cogs/*.py"
    }
    stages {
        stage('Flake8') {
            agent { label 'amd64'}
            steps {
                sh """
                    python3.7 -m venv venv && venv/bin/pip install flake8 && venv/bin/python -m flake8 --max-line-length 120 ${FLAKE_FILES}
                    rm -rf venv/
                """
                script {
                    TAG = sh(returnStdout: true, script: 'grep -i bot_version cogs/utils/bot_version.py | cut -d" " -f3 | tr -d \\"').trim()
                }
            }
        }
        stage('Docker Builds') {
            parallel {
                stage('branch') {
                    agent { label 'amd64'}
                    when {
                        not {
                            changeRequest()
                        }
                    }
                    steps {
                        script {
                            if (BRANCH_NAME == 'master') {
                                def image = docker.build("${DOCKER_REPO}:${TAG}")
                                image.push()
                                }
                                def image = docker.build("${DOCKER_REPO}:$GIT_BRANCH")
                                image.push()
                            }
                        }
                    }
                stage('pr') {
                    agent { label 'amd64'}
                    when {
                        changeRequest()
                    }
                    steps {
                        script {
                            def image = docker.build("${DOCKER_REPO}:PR_$GIT_BRANCH")
                        }
                    }
                }
            }
        }
    }
}
