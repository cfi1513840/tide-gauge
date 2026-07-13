#include <Notecard.h>
#include <STM32LowPower.h>

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
int packet_count = 0;
int buffer_index = 0;
int interval = 15;
double sensor_height = 13.90;
int packet_counts[60];
uint32_t times[60];
int distances[60];
int correlations[60];
int rssi = 0;

void setup() {
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
  //usbSerial has to be restarted following Low Power deepSleep. Commented out if not used.
  //usbSerial.end();
  delay(100);
  //usbSerial.begin(115200);
  delay(500);

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
  packet_count++;
 
  // Set report interval based on battery voltage level
  J *rsp = notecard.requestAndResponse(notecard.newRequest("card.voltage"));
  if (rsp != NULL) {
      voltage = JGetNumber(rsp, "value");
      notecard.deleteResponse(rsp);
      if (voltage < 3.6 && interval != 60) {
          interval = 60;
          packet_count = 1;    
      } else if (voltage < 3.8 && interval != 30) {
          interval = 30;
          packet_count = 1;
      } else if (interval != 15) {
          interval = 15;
          packet_count = 1;
      }
      vround = round(voltage * 100.0) / 100.0;
  }
  rsp = notecard.requestAndResponse(notecard.newRequest("card.temp"));
  if (rsp != NULL) {
      temp = JGetNumber(rsp, "value");
      notecard.deleteResponse(rsp);
      tround = round(temp * 10.0) / 10.0;
  }
  rsp = notecard.requestAndResponse(notecard.newRequest("card.wireless"));
  if (rsp != NULL) {
      J *net = JGetObject(rsp, "net");
      if (net != NULL) {
          rssi = JGetNumber(net, "rssi");     
      }
  }

  // Clear buffer before triggering new sensor readings
  while (Serial1.available() > 0) {
      Serial1.read(); 
  }
  delay(100);
  
  String allData = "";
  allData.reserve(256); // Pre-allocate memory to keep it fast

  // Request time from Notecard
  rsp = notecard.requestAndResponse(notecard.newRequest("card.time"));
  uint32_t timestamp = JGetNumber(rsp, "time");
  notecard.deleteResponse(rsp);

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
      String valStr = allData.substring(indexR + 1, indexR + 5);
      
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
  // C - Packet counter
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
  buffer_index = (packet_count % interval) -1;
  if (buffer_index == -1) {
    buffer_index = interval-1;
  }
  times[buffer_index] = timestamp;
  distances[buffer_index] = senavg;
  packet_counts[buffer_index] = packet_count;
  correlations[buffer_index] = senbr;
  // Send all accumulated measurements as a single event to Notehub at the specified interval
  //packet_count range is 1 - 180 - resets to 0 and incremented prior to next loop execution
  if (packet_count % interval == 0) {
      if (packet_count == 180) {
          packet_count = 0;
      }
      J *batch = JCreateArray();
      for (int i =0; i < interval; i++) {
        J *body = JCreateObject();
        JAddNumberToObject(body, "T", times[i]);
        JAddNumberToObject(body, "D", distances[i]);
        JAddNumberToObject(body, "C", packet_counts[i]);
        JAddNumberToObject(body, "M", correlations[i]);
        JAddItemToArray(batch, body);
        //usbSerial.print("Time: "); usbSerial.print(times[i]);
        //usbSerial.print(" Distance: "); usbSerial.print(distances[i]);
        //usbSerial.print(" Count: "); usbSerial.print(packet_counts[i]);
        //usbSerial.print(" Correlation: "); usbSerial.println(correlations[i]);
      }
      J *status = JCreateObject();
      JAddNumberToObject(status, "V", vround);
      JAddNumberToObject(status, "t", tround);
      JAddNumberToObject(status, "P", rssi);
      JAddNumberToObject(status, "H", sensor_height);
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
      }
      //usbSerial.print(" Notehub sync at interval: "); usbSerial.println(interval);
      J *req = notecard.newRequest("hub.sync");
      JAddBoolToObject(req, "allow", true); // Clears penalty boxes
      notecard.sendRequest(req);
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