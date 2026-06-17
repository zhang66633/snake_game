# Snake Game 构建文件 (Makefile)
#
# 用法:
#   make all     — 编译 C 版本 (生成 snake.exe)
#   make run-c   — 编译并运行 C 版本
#   make run-py  — 直接运行 Python 版本
#   make clean   — 删除编译产物
#

CC = gcc
CFLAGS = -Wall -Wextra -std=c99

all: snake.exe

snake.exe: snake.c
	$(CC) $(CFLAGS) snake.c -o snake.exe

run-c: snake.exe
	./snake.exe

run-py:
	python snake.py

clean:
	rm -f snake.exe
