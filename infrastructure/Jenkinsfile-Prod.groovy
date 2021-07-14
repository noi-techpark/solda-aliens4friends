pipeline {
    agent any
    
    environment {
        SERVER_PORT="1010"
        PROJECT = "alien4friends"
        DOCKER_IMAGE = '755952719952.dkr.ecr.eu-west-1.amazonaws.com/alien4friends'
        DOCKER_TAG = "prod-$BUILD_NUMBER"
    }

    stages {
        stage('Configure') {
            steps {
                sh """
                    echo 'COMPOSE_PROJECT_NAME=${PROJECT}' > .env
                    echo 'FOSSOLOGY_DB_HOST=${FOSSOLOGY_DB_HOST}' >> .env
                    echo 'FOSSOLOGY_DB_NAME=${FOSSOLOGY_DB_NAME}' >> .env
                    echo 'FOSSOLOGY_DB_USER=${FOSSOLOGY_DB_USER}' >> .env
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
                        (cd infrastructure/ansible && ansible-playbook --limit=prod deploy.yml --extra-vars "release_name=${BUILD_NUMBER} project_name=${PROJECT}")
                    """
                }
            }
        }
    }
}
