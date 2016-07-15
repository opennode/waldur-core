# Configure repositories
yum -y install epel-release
yum -y install http://opennodecloud.com/centos/7/nodeconductor-release.rpm

# Install dependencies
yum -y install mariadb-server nodeconductor-wsgi redis
    # ...or if using PostgreSQL as database backend:
    #yum -y install postgresql-server nodeconductor-wsgi redis

# Start MySQL and Redis
systemctl start mariadb
    # ...or if using PostgreSQL as database backend:
    #postgresql-setup initdb
    #systemctl start postgresql
systemctl start redis

# Create MySQL database
mysql -e "CREATE DATABASE nodeconductor CHARACTER SET = utf8"
mysql -e "CREATE USER 'nodeconductor'@'localhost' IDENTIFIED BY 'nodeconductor'"
mysql -e "GRANT ALL PRIVILEGES ON nodeconductor.* to 'nodeconductor'@'localhost'"
    # ...or if using PostgreSQL as database backend:
    #su - postgres -c "createdb -EUTF8 nodeconductor"
    #su - postgres -c "createuser nodeconductor"

# Init NodeConductor database
su - nodeconductor -c "nodeconductor migrate --noinput"

# Start Celery and Apache
systemctl start httpd
curl --head http://localhost/api/
systemctl start nodeconductor-celery
systemctl start nodeconductor-celerybeat

# (optional) Enable services to start on system boot
systemctl enable httpd
systemctl enable mariadb
    # ...or if using PostgreSQL as database backend:
    #systemctl enable postgresql
systemctl enable nodeconductor-celery
systemctl enable nodeconductor-celerybeat
systemctl enable redis
