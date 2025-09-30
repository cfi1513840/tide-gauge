// Changes for V2
//   KH: response option from RPi to change timing/spacing of sampling, allowing multiple sensors without tx collisions
//   KH: Change RF Frequency to also separate multiple sensors
//   DLS: added DEFINEs for TRIGGER_PIN and STATION_ID_NUMBER
//   DLS: added Maxbotix temperature sensor to data packet, currently just the voltage on the MB temperature input in mV
//   KH: add default delay logic in the event of packet non-ackknowledgement

#include "LoRaWan_APP.h"
#include "Arduino.h"

#define TRIGGER_PIN GPIO4
#define STATION_ID_NUMBER 1

//#define RF_FREQUENCY 915000000  // Hz
#define RF_FREQUENCY 914100000  // Hz

#define TX_OUTPUT_POWER 18  // dBm

#define LORA_BANDWIDTH 0          // [0: 125 kHz, \
                                  //  1: 250 kHz, \
                                  //  2: 500 kHz, \
                                  //  3: Reserved]
#define LORA_SPREADING_FACTOR 9  // [SF7..SF12]
#define LORA_CODINGRATE 1         // [1: 4/5, \
                                  //  2: 4/6, \
                                  //  3: 4/7, \
                                  //  4: 4/8]
#define LORA_PREAMBLE_LENGTH 8    // Same for Tx and Rx
#define LORA_SYMBOL_TIMEOUT 0     // Symbols
#define LORA_FIX_LENGTH_PAYLOAD_ON false
#define LORA_IQ_INVERSION_ON false
#define LORA_TX_TIMEOUT 5000

#define RX_TIMEOUT_VALUE 100
#define BUFFER_SIZE 256      // Define the payload size here
#define SERIAL1_TIMEOUT 100  //timeout in ms

int timetillwakeup = 38600;
char txpacket[BUFFER_SIZE];
char rxpacket[BUFFER_SIZE];

static RadioEvents_t RadioEvents;
void OnRxDone( uint8_t *payload, uint16_t size, int16_t rssi, int8_t snr );
int16_t Rssi, rxSize;
void OnTxDone(void);
void OnTxTimeout(void);
void sleep(void);
static TimerEvent_t wakeUp;

int16_t txNumber;
bool sleepMode = false;
bool rxAck = false;
bool txSend = false;
bool txComplete = false;
bool ackMode = false;
int rxCount = 0;
uint8_t packetCount;
//
// Preloaded buffer is used for test purposes, overwwritten with actual data for operations
//
uint8_t serialBuffer[256] = { "R4090\rR4103\rR0867\rR0868\rR0870\rR4097\rR4089\rR4093\rR4089\rR4089\rR4095\rR0870\rR0870\rR0867\rR0870\rR0870\rR0871\rR0868\rR4090\rR4092\r   " };
//uint8_t serialBuffer[256] = {"R0870\rR0868\rR0867\rR0868\rR0870\rR0870\rR0870\rR4093\rR0870\rR0870\rR0871\rR0870\rR0870\rR0867\rR0870\rR0870\rR0871\rR0868\rR0870\rR0870\r   "}; // Initialized for testing
uint8_t spaceChar = 32;
uint8_t RChar = 82;
uint8_t DChar = 68;
int readSize;
int senbr;
float sensum;
float senavg;
float batv;
int16_t Uval;
uint8_t statID = STATION_ID_NUMBER;
int measurements[20];
int idx1;
int idx2;
int idxm;
int ridx;
int thresh;
int matchCount = 0;
int newdelay = 0;

void onWakeUp() {
  //Serial.printf("Waking up\n");
  sleepMode = false;
}

void setup() {
  Serial.begin(9600);
  Serial1.begin(9600);
  //Serial.print("Initializing\r\n");
  pinMode(Vext, OUTPUT);
  pinMode(TRIGGER_PIN, OUTPUT);
  pinMode(ADC2, INPUT);
  pinMode(ADC3, INPUT);
  digitalWrite(Vext, HIGH);  // Original
  digitalWrite(TRIGGER_PIN, LOW);
  TimerInit(&wakeUp, onWakeUp);
  txNumber = -1;
  packetCount = 0;
  sensum = 0;
  senbr = 0;
  batv = 0;
  readSize = 0;
  sleepMode = false;
  rxAck = false;
  rxCount =0;
  txSend = false;
  txComplete = false;
  ackMode = false;
  RadioEvents.TxDone = OnTxDone;
  RadioEvents.RxDone = OnRxDone;
  RadioEvents.TxTimeout = OnTxTimeout;
  Radio.Init(&RadioEvents);
  Radio.SetChannel(RF_FREQUENCY);
  Radio.SetTxConfig(MODEM_LORA, TX_OUTPUT_POWER, 0, LORA_BANDWIDTH,
                    LORA_SPREADING_FACTOR, LORA_CODINGRATE,
                    LORA_PREAMBLE_LENGTH, LORA_FIX_LENGTH_PAYLOAD_ON,
                    true, 0, 0, LORA_IQ_INVERSION_ON, LORA_TX_TIMEOUT);
  Radio.SetRxConfig(MODEM_LORA, LORA_BANDWIDTH, LORA_SPREADING_FACTOR,
                    LORA_CODINGRATE, 0, LORA_PREAMBLE_LENGTH,
                    LORA_SYMBOL_TIMEOUT, LORA_FIX_LENGTH_PAYLOAD_ON,
                    0, true, 0, 0, LORA_IQ_INVERSION_ON, true );
}

void loop() {
  if (sleepMode) {
    lowPowerHandler();
  //
  // Wait up to 5 seconds following packet transmission for ack from receiver
  // If ack not received enter sleep mode
  //
  } else if (rxAck) {
    rxAck = false;
    //Serial.printf("request rx: %d\n", millis());
    rxCount = 0;
    Radio.Rx(0);
    while (rxCount < 10 && ackMode == false) {
      rxCount++;
      delay(500);
    }
    if (ackMode == false) {
      //Serial.printf("ack timeout, entering sleep mode %d\n", millis());
      txNumber = -1;
      timetillwakeup = 32925;
      TimerSetValue(&wakeUp, timetillwakeup);
      TimerStart(&wakeUp);
      delay(500);
      sleepMode = true;
    }
  //
  // Process ack packet if received to establish timing delay
  //
  } else if (ackMode) {
    processAck();
  //
  // Inital entry after wakeup, turn on sensor and wait 1 second
  //
  } else if (txNumber == -1) {
    rxCount = 0;
    digitalWrite(Vext, LOW);
    delay(500);
    readSize = Serial1.read(serialBuffer, SERIAL1_TIMEOUT);  // Comment out for testing
    //Serial.printf("Serial1 init read: %s\r\n", serialBuffer);
    txNumber++;
    delay(500);
    //
    // Process measurements after 20 samples have been collected at one second intervals
    //
  } else if (txNumber == 20) {
    txNumber++;
    readSize = Serial1.read(serialBuffer, SERIAL1_TIMEOUT);  // Comment out for testing
    //Serial.printf("Serial1 read: %s\r\n", serialBuffer);
    //readSize = 256; // Test only, comment out for operations
    //Serial.printf("read buffer size: %d\r\n", readSize);
    digitalWrite(Vext, HIGH); // Turn off sensor
    idx1 = 0;
    idx2 = 0;
    idxm = 0;
    //
    // Iterate through the read buffer to extract all of the "R" values
    //
    while (idx1 < readSize && serialBuffer[idx1] != spaceChar) {
      if (serialBuffer[idx1] == RChar) {
        //Serial.printf("%d ",serialBuffer[idx1]);
        idx1++;
        int distance = 0;
        //
        // Convert the ascii numeric digits to an integer value
        //
        while (idx1 < readSize && serialBuffer[idx1] >= 48 && serialBuffer[idx1] <= 57) {
          distance = distance * 10;
          distance = distance + (serialBuffer[idx1] - 48);
          idx1++;
        }
        //
        // Save measurements while ignoring erroneous values
        //
        if (distance == 0 || distance == 9999 || distance == 500) {
        } else {
          measurements[idx2] = distance;
          // Serial.printf("distance: %d\r\n", distance);
          idxm++;
          idx2++;
        }
      } else {
        idx1++;
      }
    }
    //Serial.printf("Correlation threshold: %.1f\r\n", idxm*0.60);
    //
    // Check correlation of measurements which must exceed 60% to be included in average calculation
    // Values must be in agreement with 60% of all other measurements within a range of +/- 200mm (7.87")
    //
    thresh = floor(idxm * 0.60 + 0.5);
    // Serial.printf("thresh: %d\r\n", thresh);
    for (idx1 = 0; idx1 < idxm; idx1++) {
      matchCount = 0;
      for (idx2 = 0; idx2 < idxm; idx2++) {
        if (measurements[idx2] < measurements[idx1] + 200 && measurements[idx2] > measurements[idx1] - 200) {
          matchCount++;
        }
      }
      if (matchCount >= thresh) {
        sensum = sensum + float(measurements[idx1]);
        senbr++;
      }
    }
    //
    // S - Station ID
    // V - Battery Voltage
    // C - Packet counter
    // R - Ultrasonic Range
    // M - Number of Correlated values out of the 20 measurements (optional)
    // s - Solar Panel Millivolts
    // t - Thermistor Millivolts
    sprintf(txpacket, "S%d,", statID);
    //
    // If the sensor count is non-zero, format and send the measurement message.
    // Otherwise, send an error message containing the receive buffer contents.
    //
    if (senbr != 0) {
      senavg = (sensum / senbr) + 0.5;
    } else {
      senavg = 0;
    }

    Uval = int(senavg);
    uint16_t batteryVoltage = getBatteryVoltage();
    
    #define R1 470 // kOhms
    #define R2 1000 // kOhms
    uint16_t solarVoltage = round(analogReadmV(ADC2) * (R1 + R2) / R1); // Vsolar --- R2 --- aReadmV --- R1----GND
    //uint16_t solarVoltage = round(analogReadmV(ADC2));
    uint16_t temperatureVoltage = round(analogReadmV(ADC3));

    sprintf(txpacket + strlen(txpacket), "V%d,", batteryVoltage);
    sprintf(txpacket + strlen(txpacket), "C%d,", packetCount);
    sprintf(txpacket + strlen(txpacket), "R%d,", Uval);
    sprintf(txpacket + strlen(txpacket), "M%d,", senbr);
    sprintf(txpacket + strlen(txpacket), "s%d,", solarVoltage);
    sprintf(txpacket + strlen(txpacket), "t%d", temperatureVoltage);


    //Serial.printf("Sending Packet %s\n", txpacket);
    Radio.Send((uint8_t *)txpacket, strlen(txpacket));
    //
    // Initialize counters for the next iteration, turn off sensor power and enter sleep mode
    //
    packetCount++;
    if (packetCount == 100) {
      packetCount = 0;
    }
    sensum = 0;
    senbr = 0;
  } else if (txNumber < 20) {
    //
    // Trigger the sensor reading
    //
    //Serial.printf("Trigger sensor %d\n", txNumber);
    digitalWrite(TRIGGER_PIN, HIGH);
    delay(100);
    digitalWrite(TRIGGER_PIN, LOW);
    delay(50);
    txNumber++;
    delay(840);
  }
}
void OnTxDone(void) {
  //Radio.Sleep();
  rxAck = true;
}

void OnTxTimeout(void) {
  Radio.Sleep();
  //Serial.print("TX Timeout......");
}

void OnRxDone( uint8_t *payload, uint16_t size, int16_t rssi, int8_t snr ) {
    rxAck = false;
    Rssi=rssi;
    rxSize=size;
    memcpy(rxpacket, payload, size );
    rxpacket[size]='\0';
    Radio.Sleep();
    ackMode = true;
}

void processAck() {
    ackMode = false;
    //Serial.printf("Received: %s,P%d,\r\n",rxpacket,Rssi);
    ridx = 0;
    while (ridx < rxSize) {
      if (rxpacket[ridx] == DChar) {
        ridx++;
        newdelay = 0;
        //
        // Convert the ascii numeric digits to an integer value
        //
        while (ridx < rxSize && rxpacket[ridx] >= 48 && rxpacket[ridx] <= 57) {
          newdelay = newdelay * 10;
          newdelay = newdelay + (rxpacket[ridx] - 48);
          ridx++;
        }
      } else {
        ridx++;
      }
    }
    if (newdelay != 0) {
      timetillwakeup = newdelay*1000;
    }
    txNumber = -1;
    //Serial.print("Entering sleep mode\n");
    TimerSetValue(&wakeUp, timetillwakeup);
    TimerStart(&wakeUp);
    delay(500);
    sleepMode = true;
}
