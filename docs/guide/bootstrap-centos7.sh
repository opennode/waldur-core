# Configure repositories
yum -y install epel-release
yum -y install http://opennodecloud.com/centos/7/nodeconductor-release.rpm

# Set up MySQL
yum -y install mariadb-server
systemctl start mariadb
systemctl enable mariadb

mysql -e "CREATE DATABASE nodeconductor CHARACTER SET = utf8"
mysql -e "CREATE USER 'nodeconductor'@'localhost' IDENTIFIED BY 'nodeconductor'"
mysql -e "GRANT ALL PRIVILEGES ON nodeconductor.* to 'nodeconductor'@'localhost'"

    # Alternative: set up PostgreSQL
    #yum -y install https://download.postgresql.org/pub/repos/yum/9.5/redhat/rhel-7-x86_64/pgdg-centos95-9.5-2.noarch.rpm
    #yum -y install postgresql95-server
    #/usr/pgsql-9.5/bin/postgresql95-setup initdb
    #systemctl start postgresql-9.5
    #systemctl enable postgresql-9.5
    #
    #su - postgres -c "/usr/pgsql-9.5/bin/createdb -EUTF8 nodeconductor"
    #su - postgres -c "/usr/pgsql-9.5/bin/createuser nodeconductor"

# Set up Redis
yum -y install redis
systemctl start redis
systemctl enable redis

# Set up NodeConductor
yum -y install nodeconductor-wsgi

su - nodeconductor -c "nodeconductor migrate --noinput"

systemctl start httpd
systemctl enable httpd
curl --head http://localhost/api/

systemctl start nodeconductor-celery
systemctl enable nodeconductor-celery

systemctl start nodeconductor-celerybeat
systemctl enable nodeconductor-celerybeat
