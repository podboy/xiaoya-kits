docker stop resilio
docker rm resilio

if [ $1 ]; then
	mkdir -p $1/resilio/downloads
docker run -d \
  -m 4096M \
  --log-driver none \
  --name=resilio \
  -e PUID=0 \
  -e PGID=0 \
  -e TZ=Asia/Shanghai \
  --network=host \
  -v $1/resilio:/config \
  -v $1/resilio/downloads:/downloads \
  -v $1:/sync \
  --restart=always \
  linuxserver/resilio-sync:latest

echo -e "\033[32m"
echo "安装 resilio 成功，登入的端口：8888"
echo -e "\033[0m"

if command -v crontab >/dev/null 2>&1; then
	crontab -l |grep -v sync_emby_config > /tmp/cronjob.tmp
	echo '0 6 */15 * * bash -c "$(curl --ipv4 https://docker.xiaoya.pro/sync_emby_config.sh)" -s' " $1 $2 >> $1/resilio/cron.log" >> /tmp/cronjob.tmp
	crontab /tmp/cronjob.tmp

	echo -e "\033[33m"
	echo -e '已经添加下面的记录到crontab定时任务，每15天更新一次config'
	echo '0 6 */15 * * bash -c "$(curl --ipv4 https://docker.xiaoya.pro/sync_emby_config.sh)" -s' " $1 $2 >> $1/resilio/cron.log" ' 2>&1'
	echo -e "\033[0m"
fi

else
	echo "请在命令后输入 -s /媒体库目录 再重试"
	exit 1
fi

