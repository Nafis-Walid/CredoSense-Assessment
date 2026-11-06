# ============================================================================
# Makefile for C IoT Edge Telemetry Simulator (Cross-Platform)
# ============================================================================

CC ?= gcc
CFLAGS ?= -Wall -Wextra -O2 -std=c99
SRC = simulator.c
JSON_OUT = telemetry_stream.json

ifeq ($(OS),Windows_NT)
    TARGET = simulator.exe
    RM = del /f /q 2>nul || rm -f
    PYTHON ?= python
    RUN_TARGET = $(TARGET)
else
    TARGET = simulator
    RM = rm -f
    PYTHON ?= python3
    RUN_TARGET = ./$(TARGET)
endif

.PHONY: all build run clean

all: build

build: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) $(SRC) -o $(TARGET)

run: build
	$(RUN_TARGET)
	$(PYTHON) bridge.py

clean:
	$(RM) $(TARGET) $(JSON_OUT)

