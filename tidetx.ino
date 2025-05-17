#include "LoRaWan_APP.h"
#include "Arduino.h"

#define RF_FREQUENCY                                915000000 // Hz

#define TX_OUTPUT_POWER                             14        // dBm

#define LORA_BANDWIDTH                              0         // [0: 125 kHz,
                                                              //  1: 250 kHz,
                                                              //  2: 500 kHz,
                                                              //  3: Reserved]
#define LORA_SPREADING_FACTOR                       7         // [SF7..SF12]
#define LORA_CODINGRATE                             1         // [1: 4/5,
                                                              //  2: 4/6,
                                                              //  3: 4/7,
                                                              //  4: 4/8]
#define LORA_PREAMBLE_LENGTH                        8         // Same for Tx and Rx
#define LORA_SYMBOL_TIMEOUT                         0         // Symbols
#define LORA_FIX_LENGTH_PAYLOAD_ON                  false
#define LORA_IQ_INVERSION_ON                        false


#define RX_TIMEOUT_VALUE                            1000
#define BUFFER_SIZE                                 256 // Define the payload size here
#define SERIAL1_TIMEOUT 100 //timeout in ms
#define timetillwakeup 39000
char txpacket[BUFFER_SIZE];
char rxpacket[BUFFER_SIZE];

static RadioEvents_t RadioEvents;
void OnTxDone( void );
void OnTxTimeout( void );
void sleep(void);
static TimerEvent_t wakeUp;

int16_t txNumber;
bool sleepMode = false;
uint8_t packetCount;
//
// Preloaded buffer is used for test purposes, overwwritten with actual data for operations
//
uint8_t serialBuffer[256] = {"R4090\rR4103\rR0867\rR0868\rR0870\rR4097\rR4089\rR4093\rR4089\rR4089\rR4095\rR0870\rR0870\rR0867\rR0870\rR0870\rR0871\rR0868\rR4090\rR4092\r   "};
//uint8_t serialBuffer[256] = {"R0870\rR0868\rR0867\rR0868\rR0870\rR0870\rR0870\rR4093\rR0870\rR0870\rR0871\rR0870\rR0870\rR0867\rR0870\rR0870\rR0871\rR0868\rR0870\rR0870\r   "}; // Initialized for testing
uint8_t spaceChar = 32;
uint8_t RChar = 82;
int readSize;
int senbr;
float sensum;
float senavg;
float batv;
int16_t Uval;
uint8_t statID=1;
int measurements[20];
int idx1;
int idx2;
int idxm;
int thresh;
int matchCount = 0;

void onWakeUp()
{
  //Serial.printf("Waking up.\r\n");
  sleepMode=false;
}

void setup() {
    Serial.begin(115200);
    Serial1.begin(9600);
    //Serial.print("Initializing\r\n");
    pinMode(Vext, OUTPUT);
    pinMode(GPIO5, OUTPUT);
    digitalWrite(Vext, HIGH); // Original
    digitalWrite(GPIO5, LOW); 
    TimerInit( &wakeUp, onWakeUp );
    txNumber=-1;
    packetCount=0;
    sensum = 0;
    senbr = 0;
    batv = 0;
    readSize = 0;
    sleepMode = false;
    RadioEvents.TxDone = OnTxDone;
    RadioEvents.TxTimeout = OnTxTimeout;
    Radio.Init( &RadioEvents );
    Radio.SetChannel( RF_FREQUENCY );
    Radio.SetTxConfig( MODEM_LORA, TX_OUTPUT_POWER, 0, LORA_BANDWIDTH,
                                   LORA_SPREADING_FACTOR, LORA_CODINGRATE,
                                   LORA_PREAMBLE_LENGTH, LORA_FIX_LENGTH_PAYLOAD_ON,
                                   true, 0, 0, LORA_IQ_INVERSION_ON, 3000 );
}

void loop()
{
  if (sleepMode) {
    lowPowerHandler();
  }
  //
  // Inital entry after wakeup, turn on sensor and wait 1 second
  //
  if (txNumber == -1) {
    digitalWrite(Vext, LOW);
    delay(500);
    readSize = Serial1.read(serialBuffer,SERIAL1_TIMEOUT); // Comment out for testing
    //Serial.printf("Serial1 read: %s\r\n", serialBuffer);
    txNumber++;
    delay(500);
  //
  // Process measurements after 20 samples have been collected at one second intervals
  //
  } else if (txNumber == 20) {
    readSize = Serial1.read(serialBuffer,SERIAL1_TIMEOUT); // Comment out for testing
    //Serial.printf("Serial1 read: %s\r\n", serialBuffer);
    //readSize = 256; // Test only, comment out for operations
    //Serial.printf("read buffer size: %d\r\n", readSize);
    idx1 = 0;
    idx2 = 0;
    idxm = 0;
    //
    // Iterate through the read buffer to extract all of the "R" values
    //
    while (idx1 < readSize && serialBuffer[idx1] != spaceChar) {
      if (serialBuffer[idx1] == RChar) {
        //printf("%d ",serialBuffer[idx1]);
        idx1++;
        int distance = 0;
        //
        // Convert the ascii numeric digits to an integer value
        //
        while (idx1 < readSize && serialBuffer[idx1] >= 48 && serialBuffer[idx1] <= 57) {
          distance = distance*10;
          distance = distance+(serialBuffer[idx1]-48);
          idx1++;
        }
        //
        // Save measurements while ignoring erroneous values
        //
        if (distance == 0 || distance == 9999 || distance == 500) {
        } else {
          measurements[idx2] = distance;
          //Serial.printf("distance: %d\r\n", distance);
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
    thresh = floor(idxm*0.60+0.5);
    //Serial.printf("thresh: %d\r\n", thresh);
    for (idx1=0; idx1 < idxm; idx1++) {
      matchCount = 0;
      for (idx2=0; idx2 < idxm; idx2++) {
        if (measurements[idx2] < measurements[idx1]+200 && measurements[idx2] > measurements[idx1]-200) {
          matchCount++;
        }
      }
      if (matchCount >= thresh) {
        sensum = sensum+float(measurements[idx1]);
        senbr++;
      }
    }
    //
    // In this application, the message has a 4 character preamble of 'KHDS'
    // S - Station ID
    // V - Battery Voltage
    // C - Packet counter
    // M - Number of Correlated values out of the 20 measurements (optional)
    //
    sprintf(txpacket,"KHDSS%d,",statID);
    //
    // If the sensor count is non-zero, format and send the measurement message.
    // Otherwise, send an error message containing the receive buffer contents.
    //
    if (senbr != 0) {
      senavg = (sensum/senbr)+0.5;
      Uval = int(senavg);
      //Serial.printf("Sensor samples: %d sum: %d average: %d\r\n", senbr, sensum, senavg);
		  uint16_t batteryVoltage = getBatteryVoltage();
		  sprintf(txpacket+strlen(txpacket),"V%d,",batteryVoltage);
		  sprintf(txpacket+strlen(txpacket),"C%d,",packetCount);
		  sprintf(txpacket+strlen(txpacket),"U%d",Uval);
		  //sprintf(txpacket+strlen(txpacket),"M%d\n",senbr);
    } else {
      char tempbuf[256];      
      sprintf(txpacket+strlen(txpacket), "Error-insufficient measurement correlation: ");
      for (idx1=0; idx1 <= readSize; idx1++) {
        tempbuf[idx1] = char(serialBuffer[idx1]);
      }
      sprintf(txpacket+strlen(txpacket), tempbuf);
    }
		Radio.Send( (uint8_t *)txpacket, strlen(txpacket) );
    //Serial.printf("Packet sent\r\n");
    //
    // Initialize counters for the next iteration, turn off sensor power and enter sleep mode
    //
  	txNumber = -1;
    packetCount++;
    if (packetCount == 100) {
      packetCount = 0;
    }
    sensum = 0;
    senbr = 0;
    digitalWrite(Vext, HIGH);
    delay(300);
    TimerSetValue( &wakeUp, timetillwakeup );
    TimerStart( &wakeUp );
    sleepMode = true;
  } else {
    //
    // Trigger the sensor reading
    //
    //Serial.printf("Trigger sensor\r\n");
    digitalWrite(GPIO5, HIGH);
    delay(100);
    digitalWrite(GPIO5, LOW);
    delay(50);
    txNumber++;
    delay(840);
  }
}
void OnTxDone( void )
{
	//Serial.print("TX done, entering Radio.Sleep Mode\r\n");
  Radio.Sleep();
}

void OnTxTimeout( void )
{
    Radio.Sleep( );
    Serial.print("TX Timeout......");
}
