/*
  FOREST MONITORING - NODE 1 (Sender)
  DHT11 + MQ135 sensors, 433MHz TX (send data) + 433MHz RX (receive ACK)

  Libraries required: RadioHead, DHT sensor library by Adafruit

  Wiring:
    DHT11   DATA -> D7
    MQ135   A0   -> A0
    433 TX  DATA -> D12
    433 RX  DATA -> D11
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
    Serial.println("Node 1 ready.");
  }
}

void loop() {
  float humidity    = dht.readHumidity();
  float temperature = dht.readTemperature();
  float co2ppm      = getPPM();

  if (isnan(humidity) || isnan(temperature)) {
    Serial.println("Failed to read from DHT11! Skipping this cycle.");
    delay(2000);
    return;
  }

  char tempStr[8], humStr[8], co2Str[8];
  dtostrf(temperature, 4, 1, tempStr);
  dtostrf(humidity, 4, 1, humStr);
  dtostrf(co2ppm, 4, 1, co2Str);

  char packet[40];
  snprintf(packet, sizeof(packet), "N1,%s,%s,%s", tempStr, humStr, co2Str);

  Serial.print("Sending: ");
  Serial.println(packet);

  driver.send((uint8_t *)packet, strlen(packet));
  driver.waitPacketSent();

  uint8_t buf[20];
  uint8_t buflen = sizeof(buf);
  unsigned long startWait = millis();
  bool ackReceived = false;

  while (millis() - startWait < 2000) {
    if (driver.recv(buf, &buflen)) {
      buf[buflen] = '\0';
      if (strncmp((char *)buf, "ACK", 3) == 0) {
        Serial.println("ACK received.");
        ackReceived = true;
      }
      break;
    }
  }

  if (!ackReceived) {
    Serial.println("No ACK received - will retry next cycle.");
  }

  delay(5000);
}