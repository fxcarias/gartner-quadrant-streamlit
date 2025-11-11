sudo apt update || true
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common || true 
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg || true 
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null || true
sudo apt update || true
apt-cache policy docker-ce || true
sudo apt install -y docker-ce || true
sudo usermod -aG docker ${USER} || true
sudo su - ${USER} || true
groups || true
sudo usermod -aG docker ubuntu || true
mkdir -p ~/.docker/cli-plugins/ || true
curl -SL https://github.com/docker/compose/releases/download/v2.3.3/docker-compose-linux-x86_64 -o ~/.docker/cli-plugins/docker-compose || true
chmod +x ~/.docker/cli-plugins/docker-compose || true
docker compose version || true
sudo snap install aws-cli --classic || true