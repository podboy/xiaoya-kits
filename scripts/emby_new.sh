#!/bin/bash

config_dir=/etc/xiaoya

while [[ $# -gt 0 ]]; do
    case "$1" in
        --config_dir=*)
            config_dir="${1#*=}"
            shift
            ;;
        --media_dir=*)
            media_dir="${1#*=}"
			new_media_dir=$media_dir
            shift
            ;;
        --action=*)
            action="${1#*=}"
            shift
            ;;			
        *)
            shift
            ;;
    esac
done
version="4.8.0.56"

if [ -s "$config_dir/emby_config.txt" ];then
	source "$config_dir/emby_config.txt"
        dev_dri=$(echo $dev_dri )
        resilio=$(echo $resilio )
        media_dir=$(echo $media_dir )
        mode=$(echo $mode )
        image=$(echo $image )
	if [ ! -z "$new_media_dir" ]; then
		media_dir=$new_media_dir
	fi
else
	dev_dri=no
	mode=host
	image=emby
	resilio=yes
	mkdir  -p $config_dir
	echo 'dev_dri=no' >> "$config_dir/emby_config.txt"
	echo 'mode=host' >> "$config_dir/emby_config.txt"
	echo 'image=emby' >> "$config_dir/emby_config.txt"
	echo 'version=4.8.0.56' >> "$config_dir/emby_config.txt"
	echo "media_dir=$media_dir" >> "$config_dir/emby_config.txt"
	echo "resilio=$resilio" >> "$config_dir/emby_config.txt"
	echo "" >> "$config_dir/emby_config.txt"
fi	
	
if [ "$action" == "generate_config" ]; then
	echo "请编辑 $config_dir/emby_config.txt 文件后再执行"
	echo 'bash -c "$(curl --ipv4 https://docker.xiaoya.pro/emby_new.sh)" -s' "--config_dir=$config_dir"
	exit
fi

cpu_arch=$(uname -m)
if command -v ifconfig >/dev/null 2>&1; then
        docker0=$(ifconfig docker0 | awk '/inet / {print $2}'|tr -d "addr:")
else
        docker0=$(ip addr show docker0 | awk '/inet / {print $2}' | cut -d '/' -f 1)
fi


echo "dev_dri=$dev_dri"
echo "mode=$mode"
echo "image=$image"
echo "version=$version"
echo "media_dir=$media_dir"
echo "resilio=$resilio"
echo "CPU架构=$cpu_arch"
echo "docker0=$docker0"
echo "action=$action"

if  [[ ! "$dev_dri" == 'yes' &&  ! "$dev_dri" == 'no' ]]; then
	echo "无效的选项： dev_dri= 只能是 yes 或者 no"
	exit
fi	

if  [[ ! "$resilio" == 'yes' &&  ! "$resilio" == 'no' ]]; then
	echo "无效的选项： resilio= 只能是 yes 或者 no"
	exit
fi	

if [ "$media_dir" == '' ]; then
	echo "media_dir= 不能留空"
	exit
fi				

if  [[ ! "$mode" == 'bridge' &&  ! "$mode" == 'host' ]]; then
	echo "无效的选项： mode= 只能是 bridge 或者 host"
	exit
fi				

if  [[ ! "$image" == 'emby' &&  ! "$image" == 'amilys' ]]; then
	echo "无效的选项： image= 只能是 emby 或者 amilys"
	exit
fi			

if [ "$dev_dri" == "yes" ];then
	gpu="--device /dev/dri:/dev/dri --privileged -e UID=0 -e GID=0 -e GIDLIST=0,0 -e NVIDIA_VISIBLE_DEVICES=all -e NVIDIA_DRIVER_CAPABILITIES=all"
else
	gpu=""
fi		

case $cpu_arch in
        "x86_64" | *"amd64"*)
            docker pull $image/embyserver:$version
			;;
        "aarch64" | *"arm64"* | *"armv8"* | *"arm/v8"*)
			if [ "$image" == "amilys" ]; then
                echo "amilys镜像不支持arm架构，现在使用官方镜像"
			fi	
            docker pull emby/embyserver_arm64v8:$version
            ;;
        *)
            echo "目前只支持intel64和amd64架构，你的架构是：$cpu_arch"
            exit 1
            ;;
esac

docker_exist=$(docker images |grep embyserver |grep $version)
emby_image=$(docker images |grep embyserver |grep $version |awk '{print $1}')
if [ -z "$docker_exist" ]; then
	echo "$emby_image 拉取镜像失败，请检查网络，或者翻墙后再试"
	exit 1
fi

if [[ "$action" == "all" ]] || [[ "$action" == "" ]]; then
        echo "测试xiaoya的联通性.......尝试连接 $docker_addr"
        if curl --ipv4 -siL http://127.0.0.1:5678/d/README.md |grep -v 302 |grep "x-oss-" ;then
		xiaoya_addr="http://127.0.0.1:5678"  
	elif  curl --ipv4 -siL http://$docker0:5678/d/README.md |grep -v 302 |grep  "x-oss-" ;then
		xiaoya_addr="http://$docker0:5678"
	else 	
            if [ -s $config_dir/docker_address.txt ]; then
                xiaoya_addr=$(head -n1 $config_dir/docker_address.txt)
		if ! curl --ipv4 -siL $xiaoya_addr/d/README.md |grep -v 302 |grep "x-oss-" ;then
			echo "请检查xiaoya是否正常运行后再尝试"
			exit 1
		fi		    
            else
                    echo "请先配置 $config_dir/docker_address.txt 后重试"
                    exit 1  
            fi
        fi	
fi

free_size=$(df -P $media_dir |tail -n1|awk '{print $4}')
free_size=$((free_size))
if [ "$free_size" -le 56800640 ]; then
free_size_G=$((free_size/1024/1024))
        echo "空间剩余容量不够： $free_size_G""G 小于最低要求140G"
        exit 1
fi

local_sha=$(docker inspect --format='{{index .RepoDigests 0}}' xiaoyaliu/glue:latest  |cut -f2 -d:)
remote_sha=$(curl --ipv4 -s "https://hub.docker.com/v2/repositories/xiaoyaliu/glue/tags/latest"|grep -o '"digest":"[^"]*' | grep -o '[^"]*$' |tail -n1 |cut -f2 -d:)
if [ ! "$local_sha" == "$remote_sha" ]; then
	docker rmi xiaoyaliu/glue:latest
	docker pull xiaoyaliu/glue:latest
	glue_exist=$(docker images |grep "xiaoyaliu/glue" |grep latest)
	if [ -z "$glue_exist" ]; then
		echo "xiaoyaliu/glue:latest 拉取镜像失败，请检查网络，或者翻墙后再试"
		exit 1
	fi	
fi

echo "清理媒体库原来保存的元数据和配置......."
mkdir -p $media_dir/temp
rm -rf $media_dir/config 
echo "清理完成"
mkdir -p $media_dir/xiaoya
mkdir -p $media_dir/config
chmod 777 $media_dir
chown root:root $media_dir
if [[ "$action" == "all" ]] || [[ "$action" == "" ]]; then
	docker run -i --security-opt seccomp=unconfined --rm --net=host -v $media_dir:/media -v $config_dir:/etc/xiaoya -e LANG=C.UTF-8  xiaoyaliu/glue:latest /update_all.sh $xiaoya_addr
fi

if [ "$action" == "unzip" ]; then
	docker run -i --security-opt seccomp=unconfined --rm --net=host -v $media_dir:/media -v $config_dir:/etc/xiaoya -e LANG=C.UTF-8  xiaoyaliu/glue:latest /unzip.sh $xiaoya_addr
fi

if [ -f "$media_dir/config/data/device.txt" ]; then
	if grep -q "1999bfd1661041cd85ff5e260bc04c06" $media_dir/config/data/device.txt; then
		rm -f $media_dir/config/data/device.txt
	fi
fi

echo "http://$docker0:6908" > $config_dir/emby_server.txt
echo e825ed6f7f8f44ffa0563cddaddce14d > $config_dir/infuse_api_key.txt
chmod -R 777 $media_dir/*

if ! grep xiaoya.host /etc/hosts; then
	if [ "$mode" == "host" ]; then 
		echo -e "127.0.0.1\txiaoya.host\n" >> /etc/hosts
		xiaoya_host="127.0.0.1"
	fi
	if [ "$mode" == "bridge" ]; then 
		echo -e "$docker0\txiaoya.host\n" >> /etc/hosts
		xiaoya_host="$docker0"
	fi	
else
	xiaoya_host=$(grep xiaoya.host /etc/hosts |awk '{print $1}' |head -n1)	
fi

docker stop emby 2>/dev/null
docker rm emby 2>/dev/null
echo "开始安装Emby容器....."
rm $config_dir/nsswitch.conf 2>/dev/null
rmdir $config_dir/nsswitch.conf 2>/dev/null
echo -e "hosts:\tfiles dns" > $config_dir/nsswitch.conf
echo -e "networks:\tfiles" >> $config_dir/nsswitch.conf
#wget -q -O /tmp/Emby.Server.Implementations.dll https://docker.xiaoya.pro/Emby.Server.Implementations.dll
case $cpu_arch in
	"x86_64" | *"amd64"*)
		if [ $mode == "host" ]; then
			docker run -d --name emby -v $media_dir/config:/config -v $media_dir/xiaoya:/media -v $config_dir/nsswitch.conf:/etc/nsswitch.conf --network=host --add-host="xiaoya.host:$xiaoya_host" $gpu --user 0:0 -v UID=0 -v GID=0 -v GLIST=0 --restart always $image/embyserver:$version
		fi
		if [ $mode == "bridge" ]; then
			docker run -d --name emby -v $media_dir/config:/config -v $media_dir/xiaoya:/media -v $config_dir/nsswitch.conf:/etc/nsswitch.conf -p 6908:6908 --add-host="xiaoya.host:$xiaoya_host" $gpu --user 0:0 -v UID=0 -v GID=0 -v GLIST=0 --restart always $image/embyserver:$version
		fi
		echo "一键全家桶全部安装完成"
		;;
	"aarch64" | *"arm64"* | *"armv8"* | *"arm/v8"*)
		if [ $mode == "host" ]; then	
	        docker run -d --name emby -v $media_dir/config:/config -v $media_dir/xiaoya:/media -v $config_dir/nsswitch.conf:/etc/nsswitch.conf --network=host --add-host="xiaoya.host:$xiaoya_host" $gpu --user 0:0 -v UID=0 -v GID=0 -v GLIST=0 --restart always emby/embyserver_arm64v8:$version
		fi
		if [ $mode == "bridge" ]; then	
	        docker run -d --name emby -v $media_dir/config:/config -v $media_dir/xiaoya:/media -v $config_dir/nsswitch.conf:/etc/nsswitch.conf -p 6908:6908 --add-host="xiaoya.host:$xiaoya_host" $gpu --user 0:0 -v UID=0 -v GID=0 -v GLIST=0 --restart always emby/embyserver_arm64v8:$version
		fi
		echo "一键全家桶全部安装完成"
        ;;
	*)
		echo "目前只支持intel64和amd64架构，你的架构是：$cpu_arch"
		exit 1
		;;
esac		

start_time=$(date +%s)
TARGET_LOG_LINE_SUCCESS="All entry points have started"
while true; do
	line=$(docker logs emby 2>&1 | tail -n 10)
	echo $line
	if [[ "$line" == *"$TARGET_LOG_LINE_SUCCESS"* ]]; then
        break
	fi
	current_time=$(date +%s)
	elapsed_time=$((current_time - start_time))
	if [ "$elapsed_time" -gt 300 ]; then
		echo "Emby未正常启动超时5分钟，终止程序"
		break
	fi	
	sleep 3
done

if ! curl --ipv4 -I -s http://$docker0:2345/ | grep -q "302"; then 
	echo "重启 xiaoya"
	docker restart xiaoya 2>/dev/null
fi       

if [ "$resilio" == "yes" ];then	
	echo "开始安装 Resilio 同步软件"
	bash -c "$(curl --ipv4 https://docker.xiaoya.pro/resilio.sh)" -s $media_dir $config_dir
fi

