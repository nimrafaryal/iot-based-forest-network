/*
  FOREST MONITORING - NODE 2 (Relay)
  - Receives data from Node 1
  - Sends ACK back to Node 1
  - Reads its own sensors
  - Broadcasts combined data to Gateway (same TX module)

  Libraries required: RadioHead, DHT sensor library by Adafruit

  Wiring:
    DHT11   DATA -> D7
    MQ135   A0   -> A0
    433 RX  DATA -> D11
    433 TX  DATA -> D12
*/

#include <DHT.h>
#include <math.h>
#include <RH_ASK.h>
#include <SPI.h>

#define DHTPIN     7
#define DHTTYPE    DHT11
#define MQ135PIN   A0

DHT dht(DHTPIN, DHTTYPE);

#define RLOAD      10.0
#define RZERO      76.63
#define PARA       116.6020
#define PARB       2.769034

RH_ASK driver(2000, 11, 12);

float getResistance() {
  int raw = analogRead(MQ135PIN);
  float voltage = raw / 1024.0 * 5.0;
  return ((5.0 * RLOAD) / voltage) - RLOAD;
}

float getPPM() {
  float resistance = getResistance();
  return PARA * pow((resistance / RZERO), -PARB);
}

void setup() {
  Serial.begin(9600);
  dht.begin();
  if (!driver.init()) {
    Serial.println("RF driver init failed!");
  } else {
    Serial.println("Node 2 ready, listening for Node 1...");
  }
}

void loop() {
  uint8_t buf[40];
  uint8_t buflen = sizeof(buf);

  if (driver.recv(buf, &buflen)) {
    buf[buflen] = '\0';
    String node1Data = String((char *)buf);
    Serial.print("Received from Node 1: ");
    Serial.println(node1Data);

    const char *ack = "ACK";
    driver.send((uint8_t *)ack, strlen(ack));
    driver.waitPacketSent();
    Serial.println("ACK sent to Node 1.");

    delay(100);

    float humidity    = dht.readHumidity();
    float temperature = dht.readTemperature();
    float co2ppm      = getPPM();

    char node2Part[40];

    if (isnan(humidity) || isnan(temperature)) {
      Serial.println("DHT11 read failed on Node 2, sending Node1 data only.");
      snprintf(node2Part, sizeof(node2Part), "N2,NA,NA,NA");
    } else {
      char tempStr[8], humStr[8], co2Str[8];
      dtostrf(temperature, 4, 1, tempStr);
      dtostrf(humidity, 4, 1, humStr);
      dtostrf(co2ppm, 4, 1, co2Str);
      snprintf(node2Part, sizeof(node2Part), "N2,%s,%s,%s", tempStr, humStr, co2Str);
    }

    String combined = node1Data + "|" + String(node2Part);
    Serial.print("Forwarding to Gateway: ");
    Serial.println(combined);

    driver.send((uint8_t *)combined.c_str(), combined.length());
    driver.waitPacketSent();

    Serial.println("Data forwarded to Gateway.");
  }
}