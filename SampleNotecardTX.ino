#include <Notecard.h>
#include <STM32LowPower.h>
#include <IWatchdog.h>

#define usbSerial Serial
Notecard notecard;

int measurements[20];
int idx1 = 0;
int idx2 = 0;
int idxm = 0;
int senbr = 0;
int sensum = 0;
int senavg = 0;
int thresh = 0;
int matchCount = 0;
int readings[20];
int count = 0;
int indexR = -1;
double voltage = 0;
double vround = 0;
double temp = 0;
double tround = 0;
int distance = 0;
uint32_t one_minute_timer = 0;
uint32_t last_send_timer_count = 0;
int buffer_index = 0;
int interval = 15;
const char *sensor_id = "PRO";
uint32_t times[60];
int distances[60];
int correlations[60];
int rssi = 0;
String allData;
String valStr;
uint32_t timestamp = 0;

const float HYSTERESIS = 0.05;  // 50mV deadband

// Thresholds for switching DOWN (stricter - battery is draining)
const float THRESH_VLOW  = 3.45;
const float THRESH_LOW  = 3.60;
const float THRESH_MID  = 3.75;
const float THRESH_HIGH  = 3.90;


// Thresholds for switching back UP (relaxed - voltage recovered)
const float THRESH_HIGH_RECOVER = THRESH_HIGH + HYSTERESIS;
const float THRESH_MID_RECOVER = THRESH_MID + HYSTERESIS;
const float THRESH_LOW_RECOVER = THRESH_LOW + HYSTERESIS;
const float THRESH_VLOW_RECOVER = THRESH_VLOW + HYSTERESIS;

int new_interval;



void setup() {
    //IWatchdog.begin(10 * 1000 * 1000); // 10s

    allData.reserve(256); // Pre-allocate memory to keep it fast
    valStr.reserve(6);

    // Initialize 3V3 Regulator to default state
    pinMode(ENABLE_3V3, OUTPUT);
    pinMode(DISCHARGE_3V3, OUTPUT);
    digitalWrite(DISCHARGE_3V3, DISABLE_DISCHARGING);
    digitalWrite(ENABLE_3V3, HIGH);

    //usbSerial.begin(115200);
    // Sensor setup
    pinMode(D5, OUTPUT);      // Trigger pin
    digitalWrite(D5, LOW);    // Keep sensor quiet to start
    Serial1.begin(9600);      // MB7388 default baud rate is 9600

    // Initialize Notecard
    notecard.begin();
    LowPower.begin();

    // Cellular setup
    J *req = notecard.newRequest("hub.set");
    if (req != NULL) {
        JAddStringToObject(req, "product", "com.gmail.cfi1513840:bbi_tide_station"); 
        JAddStringToObject(req, "mode", "manual"); 
        notecard.sendRequest(req);
    }
}
void loop() {
  //IWatchdog.reload();

  //usbSerial has to be restarted following Low Power deepSleep. Commented out if not used.
  //usbSerial.end();
  delay(100);
  //usbSerial.begin(115200);
  delay(500);
  Serial1.end();
  Serial1.begin(9600);
  Wire.end();
  Wire.begin();
  notecard.begin();

  // Initialize variables
  voltage = 0;
  temp = 0;
  distance = 0;
  idx2 = 0;
  idxm = 0;
  senbr = 0;
  sensum = 0;
  senavg = 0;
  thresh = 0;
  matchCount = 0;
  count = 0;
  indexR = -1;
  allData = "";
  memset(readings, 0, sizeof(readings));
  memset(measurements, 0, sizeof(measurements));
  one_minute_timer++;

  // Set report interval based on battery voltage level
  J *rsp = notecard.requestAndResponse(notecard.newRequest("card.voltage"));
  if (rsp != NULL) {
      voltage = JGetNumber(rsp, "value");
      notecard.deleteResponse(rsp);
      if (voltage < THRESH_VLOW) {
          new_interval = 1440;
      } else if (voltage < THRESH_VLOW_RECOVER && interval == 1440) {
          new_interval = 1440;
      } else if (voltage < THRESH_LOW) {
          new_interval = 120;
      } else if (voltage < THRESH_MID_RECOVER && interval == 120) {
          new_interval = 120;
      } else if (voltage < THRESH_MID) {
          new_interval = 60;
      } else if (voltage < THRESH_MID_RECOVER && interval == 60) {
          new_interval = 60;
      } else if (voltage < THRESH_HIGH) {
          new_interval = 30;
      } else if (voltage < THRESH_HIGH_RECOVER && interval == 30) {
          new_interval = 30;
      } else {
          new_interval = 15;
      }
      if (new_interval != interval) {
          interval = new_interval;
      }
      vround = round(voltage * 100.0) / 100.0;
  } else {
      // usbSerial.println("ERR: newRequest returned NULL");
  }
  rsp = notecard.requestAndResponse(notecard.newRequest("card.temp"));
  if (rsp != NULL) {
      temp = JGetNumber(rsp, "value");
      notecard.deleteResponse(rsp);
      tround = round(temp * 10.0) / 10.0;
  } else {
    // usbSerial.println("ERR: newRequest returned NULL");
  } 
  rsp = notecard.requestAndResponse(notecard.newRequest("card.wireless"));
  if (rsp != NULL) {
      J *net = JGetObject(rsp, "net");
      if (net != NULL) {
          rssi = JGetNumber(net, "rssi");     
      }
      notecard.deleteResponse(rsp);
  } else {
      // usbSerial.println("ERR: newRequest returned NULL");
  }

  // Clear buffer before triggering new sensor readings
  while (Serial1.available() > 0) {
      Serial1.read(); 
  }
  delay(100);
  
  // Request time from Notecard
  rsp = notecard.requestAndResponse(notecard.newRequest("card.time"));
  if (rsp != NULL) {
      timestamp = JGetNumber(rsp, "time");
      notecard.deleteResponse(rsp);
  } else {
      // usbSerial.println("ERR: newRequest returned NULL");
  }
// Trigger 20 sensor readings at one second intervals
  //usbSerial.println("Starting 20-sample burst...");
  
  for (int i = 0; i < 20; i++) {
      // Trigger one ping
      digitalWrite(D5, HIGH);      
      delay(100); // Short high pulse to trigger
      digitalWrite(D5, LOW);       
      
      // Wait for the sensor to ping and transmit (~100ms-150ms)
      delay(150); 
      
      // Get the Rxxxx\r string
      while (Serial1.available() > 0) {
          allData += (char)Serial1.read();
      }
      delay(750);
  }
  disable3V3Regulator();
  // Print sample string
  //usbSerial.print(" Data Received: [");
  //usbSerial.print(allData);
  //usbSerial.println("]");

  // Search through the string for every 'R'
  while ((indexR = allData.indexOf('R', indexR + 1)) != -1 && count < 20) {
      // Grab the 4 characters after the 'R' (e.g., "0450")
      valStr = allData.substring(indexR + 1, indexR + 5);
      
      // Convert to integer and store it
      readings[count] = valStr.toInt();
      count++;
  }

  // Filter and average samples
  for (idx1 = 0; idx1 < count; idx1++) {
  //
  // Save measurements while ignoring erroneous values
  //
      if (readings[idx1] == 0 || readings[idx1] == 9999 || readings[idx1] == 500) {
      } else {
          measurements[idx2] = readings[idx1];
          // Serial.printf("distance: %d\r\n", readings[idx1]);
          idxm++;
          idx2++;
      }
  }
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
  // V - Battery Voltage
  // R - Ultrasonic Range
  // M - Number of Correlated values out of the 20 measurements (optional)

  // format and save the measurement measurement.
  //
  if (senbr != 0) {
      senavg = (sensum / senbr) + 0.5;
  } else {
      senavg = 0;
  }
  // Add this sensor packet to the array
  times[buffer_index] = timestamp;
  distances[buffer_index] = senavg;
  correlations[buffer_index] = senbr;
  buffer_index++;
  // Send all accumulated measurements as a single event to Notehub at the specified interval
  if (one_minute_timer - last_send_timer_count >= interval) {
      J *batch = JCreateArray();
      for (int i =0; i < buffer_index; i++) {
        J *body = JCreateObject();
        JAddNumberToObject(body, "T", times[i]);
        JAddNumberToObject(body, "D", distances[i]);
        JAddNumberToObject(body, "M", correlations[i]);
        JAddItemToArray(batch, body);
        //usbSerial.print("Time: "); usbSerial.print(times[i]);
        //usbSerial.print(" Distance: "); usbSerial.print(distances[i]);
        //usbSerial.print(" Correlation: "); usbSerial.println(correlations[i]);
      }
      J *status = JCreateObject();
      JAddNumberToObject(status, "V", vround);
      JAddNumberToObject(status, "t", tround);
      JAddNumberToObject(status, "P", rssi);
      JAddStringToObject(status, "S", sensor_id);
      J *note = notecard.newRequest("note.add");
      if (note != NULL) {
        JAddStringToObject(note, "file", "sensors.qo");
        J *body = JCreateObject();
        JAddItemToObject(body, "status", status);
        JAddItemToObject(body, "measurements", batch);
        JAddItemToObject(note, "body", body);      
        //char *json_string = JPrint(note);
        //usbSerial.println(json_string);
        //free(json_string);
        notecard.sendRequest(note);
      } else {
        // usbSerial.println("ERR: newRequest returned NULL");
        JDelete(batch);   
        JDelete(status); 
      }

      //usbSerial.print(" Notehub sync at interval: "); usbSerial.println(interval);
      J *req = notecard.newRequest("hub.sync");
      if (req != NULL) {
          JAddBoolToObject(req, "allow", true); // Clears penalty boxes
          notecard.sendRequest(req);
      } else {
        // usbSerial.println("ERR: newRequest returned NULL");
      }
      buffer_index = 0;
      last_send_timer_count = one_minute_timer;
      delay(2000);
      LowPower.deepSleep(36375);
      //delay(38975);
      enable3V3Regulator();
      delay(500);
  } else {
      LowPower.deepSleep(38375); // Wait ~1 minute (adjusted for the logic delays)
      //delay(38975);
      enable3V3Regulator();
      delay(500);
  }
}

void disable3V3Regulator() {
  digitalWrite(ENABLE_3V3, LOW);
  digitalWrite(DISCHARGE_3V3, ENABLE_DISCHARGING);
}

void enable3V3Regulator() {
  digitalWrite(DISCHARGE_3V3, DISABLE_DISCHARGING);
  digitalWrite(ENABLE_3V3, HIGH);
}