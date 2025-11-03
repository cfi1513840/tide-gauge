/**
 * Receive LoRa-modulation packets with a sequence number, add RSSI
 * and output on the serial port.
 *
*/

#include <heltec_unofficial.h>
#include <string>

// Pause between transmited packets in seconds.
// Set to zero to only transmit a packet when pressing the user button
// Will not exceed 1% duty cycle, even if you set a lower value.
#define PAUSE               30

// Frequency in MHz. Keep the decimal point to designate float.
// Check your own rules and regulations to see what is legal where you are.
//#define FREQUENCY           866.3       // for Europe
//#define FREQUENCY           915.0       // for US
#define FREQUENCY           914.1       // for US

// LoRa bandwidth. Keep the decimal point to designate float.
// Allowed values are 7.8, 10.4, 15.6, 20.8, 31.25, 41.7, 62.5, 125.0, 250.0 and 500.0 kHz.
//#define BANDWIDTH           250.0
#define BANDWIDTH           125.0

// Number from 5 to 12. Higher means slower but higher "processor gain",
// meaning (in nutshell) longer range and more robust against interference. 
#define SPREADING_FACTOR    9

// Transmit power in dBm. 0 dBm = 1 mW, enough for tabletop-testing. This value can be
// set anywhere between -9 dBm (0.125 mW) to 22 dBm (158 mW). Note that the maximum ERP
// (which is what your antenna maximally radiates) on the EU ISM band is 25 mW, and that
// transmissting without an antenna can damage your hardware.
#define TRANSMIT_POWER      18

String rxdata = "test";
volatile bool rxFlag = false;
long station = 1;
long counter = 0 ;
uint64_t proc_time;
uint64_t start_time;
int16_t Rssi;
int16_t test;
char txout[16];

void setup() {
  start_time = millis()/1000;
  heltec_setup();
  Serial.begin(9600);
  RADIOLIB_OR_HALT(radio.begin());
  // Set the callback function for received packets
  radio.setDio1Action(rx);
  // Set radio parameters
  RADIOLIB_OR_HALT(radio.setFrequency(FREQUENCY));
  RADIOLIB_OR_HALT(radio.setBandwidth(BANDWIDTH));
  RADIOLIB_OR_HALT(radio.setSpreadingFactor(SPREADING_FACTOR));
  RADIOLIB_OR_HALT(radio.setOutputPower(TRANSMIT_POWER));
  // Start receiving
  radio.setDio1Action(rx);
  RADIOLIB_OR_HALT(radio.startReceive(RADIOLIB_SX126X_RX_TIMEOUT_INF));
}

void loop() {
  heltec_loop();
  // If a packet was received, output it and the RSSI and initiate new read
  if (rxFlag) {
    rxFlag = false;
    radio.readData(rxdata);
    
    if (_radiolib_status == RADIOLIB_ERR_NONE) {
      Rssi = radio.getRSSI();
      Serial.printf("%s,P%d\n", rxdata.c_str(),Rssi);
      delay(1000);
      tx();
      delay(100);
      radio.setDio1Action(rx);
      RADIOLIB_OR_HALT(radio.startReceive(RADIOLIB_SX126X_RX_TIMEOUT_INF));
    }
  } else {
    delay(975);
  }
}
//
// Send ack packet to sensor with new delay value
//
void tx() {
   proc_time = (millis()/1000 - start_time) % 60;
    if (rxdata[0] == 'S') {
     if (rxdata[1] == '1') {
       station = 1;
     } else if (rxdata[1] == '2') {
       station = 2;
     } else if (rxdata[1] == '3') {
       station = 3;
     }
    int delay = ((station*15)-proc_time)+60;
    sprintf(txout,"T%d,", station);
    sprintf(txout+strlen(txout),"D%d", delay);
    Serial.printf("txout: ' %s\n",txout);
    radio.clearDio1Action();
    RADIOLIB(radio.transmit(txout));
  }
}
// Can't do Serial or display things here, takes too much time for the interrupt
void rx() {
  rxFlag = true;
}
