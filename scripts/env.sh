#!/bin/bash
project_path=$1
# 安装 python 源
yum install https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm
# 安装 python3
yum install python36

python36 --version

if [ $? -ne 0 ]; then
    echo "安装 python36 失败, 未找到 python36"
    exit 1
fi

yum install python3-pip

if [ $? -ne 0 ]; then
    echo "安装 pip3 失败"
    exit 1
fi

##
# 最好的方式是使用 python 虚拟环境, 但安装起来可
# 能会遇到各种问题, 暂时不写在里面.
##

pip3 install -r ../requirement.txt

# 安装 supervisor 守护进行
yum install epel-release
yum install -y supervisor
systemctl enable supervisord
systemctl start supervisord

# 创建 supervisor 基础文件
mkdir -p /etc/supervisord.d/

cat >/etc/supervisord.d/wallet-server.ini<<EOF
[program:wallet-server]
command=python3 $project_path/run_server
user=root
stdout_logfile=/var/log/supervisor/wallet-server.log
redirect_stderr=true
stdout_logfile_maxbytes=500MB
EOF

# 启动服务
supervisorctl update
supervisorctl start wallet-server

