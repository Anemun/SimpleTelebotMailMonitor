pipeline {
    agent { label 'docker'}
    environment {
        DOCKER_IMAGE = "jackithub/simplemailmonitor:${BUILD_NUMBER}"
        CONTAINER_NAME = "${params.containerName}"
    }
    stages {        
        stage ('1. Build image'){
            steps {
                sh "docker build -t $DOCKER_IMAGE -f Dockerfile ."
            }
        }
        stage ('2. Push image') {
            steps {
                withDockerRegistry([credentialsId: 'dockerHub', url: ""]) {
                sh "docker push $DOCKER_IMAGE"
                }   
            }
        }
        stage ('3. Deploy image to remote server') {
            stages {
                stage ('3.1 Stop current container') {
                    steps {
                        sshagent(credentials: ['SSHroot']) {
                            withCredentials([string(credentialsId: 'ServerIP', variable: 'IP')]) {
                                sh "ssh -o StrictHostKeyChecking=no $IP docker stop $CONTAINER_NAME || true && ssh -o StrictHostKeyChecking=no $IP docker rm $CONTAINER_NAME || true"                              
                            }
                        }
                    }
                }
                stage ('3.2 Run new container') {
                    steps {
                        sshagent(credentials: ['SSHroot']) {
                            withCredentials([usernamePassword(credentialsId: 'dockerHub', usernameVariable: 'USERNAME', passwordVariable: 'PASSWORD'),
                                    string(credentialsId: 'ServerIP', variable: 'IP'),
                                    string(credentialsId: 'NmailMonitorFromMailbox', variable: 'NmailMonitorFromMailbox'),
                                    string(credentialsId: 'NmailMonitorFromMailboxPass', variable: 'NmailMonitorFromMailboxPass'),
                                    string(credentialsId: 'NmailMonitorSmtpServer', variable: 'NmailMonitorSmtpServer'),
                                    string(credentialsId: 'NmailMonitorImapServer', variable: 'NmailMonitorImapServer'),
                                    string(credentialsId: 'NmailMonitorToMailbox', variable: 'NmailMonitorToMailbox'),
                                    string(credentialsId: 'NmailMonitorBotToken', variable: 'NmailMonitorBotToken'),
                                    string(credentialsId: 'NmailMonitorChatId', variable: 'NmailMonitorChatId'),
                                    string(credentialsId: 'NmailMonitorSubjectCode', variable: 'NmailMonitorSubjectCode')]) {
                                sh "ssh -o StrictHostKeyChecking=no $IP docker login -u $USERNAME -p $PASSWORD"
                                sh "ssh -o StrictHostKeyChecking=no $IP docker run -d --restart always --name $CONTAINER_NAME $DOCKER_IMAGE 
                                    --fromMailbox $NmailMonitorFromMailbox 
                                    --fromMailboxPass $NmailMonitorFromMailboxPass 
                                    --smtpServer $NmailMonitorSmtpServer 
                                    --imapServer $NmailMonitorImapServer 
                                    --toMailbox $NmailMonitorToMailbox 
                                    --botToken $NmailMonitorBotToken 
                                    --botChatId $NmailMonitorChatId 
                                    --subjectCode $NmailMonitorSubjectCode"
                            }
                        }
                    }
                }
            }
        }
    }
}