# Configure repositories
yum -y install epel-release
yum -y install http://opennodecloud.com/centos/7/nodeconductor-release.rpm
    # ...and if using PostgreSQL as database backend:
    #yum -y install https://download.postgresql.org/pub/repos/yum/9.5/redhat/rhel-7-x86_64/pgdg-centos95-9.5-2.noarch.rpm

# Install dependencies
yum -y install mariadb-server nodeconductor-wsgi redis
    # ...or if using PostgreSQL as database backend:
    #yum -y install postgresql95-server nodeconductor-wsgi redis

# Start MySQL and Redis
systemctl start mariadb
    # ...or if using PostgreSQL as database backend:
    #/usr/pgsql-9.5/bin/postgresql95-setup initdb
    #systemctl start postgresql-9.5
systemctl start redis

# Create MySQL database
mysql -e "CREATE DATABASE nodeconductor CHARACTER SET = utf8"
mysql -e "CREATE USER 'nodeconductor'@'localhost' IDENTIFIED BY 'nodeconductor'"
mysql -e "GRANT ALL PRIVILEGES ON nodeconductor.* to 'nodeconductor'@'localhost'"
    # ...or if using PostgreSQL as database backend:
    #su - postgres -c "/usr/pgsql-9.5/bin/createdb -EUTF8 nodeconductor"
    #su - postgres -c "/usr/pgsql-9.5/bin/createuser nodeconductor"

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
    #systemctl enable postgresql-9.5
systemctl enable nodeconductor-celery
systemctl enable nodeconductor-celerybeat
systemctl enable redis
