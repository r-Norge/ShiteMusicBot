pipeline {
    agent none
    environment {
        GIT_REPO = 'Ev-1/ShiteMusicBot'
        DOCKER_REPO = 'rnorge/music'
        TAG=""
        FLAKE_FILES = "bot.py cogs/*.py cogs/utils/*.py"
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
                    SBranch = sh(returnStdout: true, script: 'echo ${GIT_BRANCH} | sed "s#/#_#"').trim()
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
                                def image = docker.build("${DOCKER_REPO}:${TAG}-amd64")
                                image.push("${TAG}-amd64")
                                image.push("latest-amd64")
                            }
                            else {
                                def image = docker.build("${DOCKER_REPO}:${SBranch}-amd64")
                                image.push()
                                }
                            }
                        }
                    }
                stage('pr') {
                    agent { label 'amd64'}
                    when { changeRequest() }
                    steps {
                        script {
                            def image = docker.build("${DOCKER_REPO}:PR_$GIT_BRANCH-amd64")
                        }
                    }
                }
            }
        }
        stage('GitHub Release') {
            when { branch 'master' }
            agent { label 'amd64'}
            steps {
                withCredentials([usernameColonPassword(credentialsId: 'RoxBot-Dev Github', variable: 'GitCred')]) {
                    sh """
                        git remote set-url origin "https://${GitCred}@github.com/${GIT_REPO}.git"
                        git tag ${TAG}
                        git push --tags
                    """
                    }
            }
        }
    }
}
