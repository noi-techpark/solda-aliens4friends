pipeline {
    agent any
    
    environment {
        SERVER_PORT="1010"
        DOCKER_FOSSOLOGY_IMAGE="755952719952.dkr.ecr.eu-west-1.amazonaws.com/solda-fossology"
        DOCKER_TOOLCHAIN_IMAGE="755952719952.dkr.ecr.eu-west-1.amazonaws.com/solda-toolchain"
        DOCKER_TAG = "test-$BUILD_NUMBER"
        PROJECT = "solda"
        FOSSOLOGY_DB_PASSWORD=credentials('alien4friends-testdb-password')
    }

    stages {
        stage('Configure') {
            steps {
                sh """
                    echo 'COMPOSE_PROJECT_NAME=${PROJECT}' > .env
                    echo 'DOCKER_FOSSOLOGY_IMAGE=${DOCKER_FOSSOLOGY_IMAGE}' >> .env
                    echo 'DOCKER_TOOLCHAIN_IMAGE=${DOCKER_TOOLCHAIN_IMAGE}' >> .env
                    echo 'DOCKER_TAG=${DOCKER_TAG}' >> .env
                    echo 'LOG_LEVEL=debug' >> .env
                    echo 'FOSSOLOGY_DB_HOST=test-pg-bdp.co90ybcr8iim.eu-west-1.rds.amazonaws.com' >> .env
                    echo 'FOSSOLOGY_DB_NAME=alien4friends' >> .env
                    echo 'FOSSOLOGY_DB_USER=alien4friends' >> .env
                    echo 'FOSSOLOGY_DB_PASSWORD=${FOSSOLOGY_DB_PASSWORD}' >> .env
                """
            }
        }
        stage('Test & Build') {
            steps {
                sh """
                    aws ecr get-login --region eu-west-1 --no-include-email | bash
                    docker-compose --no-ansi -f infrastructure/docker-compose.build.yml build --pull
                    docker-compose --no-ansi -f infrastructure/docker-compose.build.yml push
                """
            }
        }
        stage('Deploy') {
            steps {
               sshagent(['jenkins-ssh-key']) {
                    sh """
                        (cd infrastructure/ansible && ansible-galaxy install -f -r requirements.yml)
                        (cd infrastructure/ansible && ansible-playbook --limit=test deploy.yml --extra-vars "release_name=${BUILD_NUMBER} project_name=${PROJECT}")
                    """
                }
            }
        }
    }
}
