.PHONY install run deploy backup clean logs

install
	pip install -r requirements.txt

run
	python bot.py

dev
	python bot.py

deploy
	.deploy.sh

backup
	tar -czf backup_$$(date +%Y%m%d_%H%M%S).tar.gz data

clean
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name .pyc -delete
	rm -rf datahosted_files

logs
	tail -f bot.log

setup
	cp .env.example .env
	@echo Edit .env with your settings
	mkdir -p datahosted_files
	pip install -r requirements.txt

test
	python -c from config import Settings; s = Settings(); print(s.display())