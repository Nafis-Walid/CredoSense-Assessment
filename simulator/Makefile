CC ?= gcc
CFLAGS ?= -Wall -Wextra -std=c99 -pedantic -O2
TARGET = simulator

all: $(TARGET)

$(TARGET): simulator.c
	$(CC) $(CFLAGS) simulator.c -o $(TARGET)

run: $(TARGET)
	./$(TARGET)

clean:
	rm -f $(TARGET) $(TARGET).exe *.o telemetry_stream.json simulator/telemetry_stream.json

.PHONY: all run clean
