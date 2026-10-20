/*
  Inclinômetro só com acelerômetro (MPU-6050 / MPU-6500 / módulo GY-521), sem biblioteca do sensor.

  O ângulo vem direto da gravidade, sem integrar o giroscópio e sem gate, então não há deriva:
    pitch = atan2(-ax, sqrt(ay^2 + az^2))     (+ = nariz para baixo)
    roll  = atan2(ay, az)                     (+ = lado direito para baixo)
  com offset e ganho de cada eixo corrigidos (calibração de 6 posições, na EEPROM) e um passa-baixa de 1a ordem
  de 0,2 s no vetor de aceleração. O giroscópio não é usado.

  Ligações (Nano/Uno): VCC, GND, SDA->A4, SCL->A5. Endereço I2C 0x68 (AD0 em GND).
  Orientação assumida: X = frente do carro, Y = esquerda, Z = para cima. Monte o módulo alinhado com o carro.

  PROTOCOLO SERIAL (115200 baud, linhas terminadas em '\n', colunas separadas por ';')
  Tudo que o Arduino envia como texto é MAIÚSCULO, sem acento, com '_' no lugar de espaço.

  Saída (Arduino -> PC), 100 Hz:
    #D;t_ms;pitch;roll;ax_g;ay_g;az_g;temp_c;\n     (ax/ay/az: aceleração já calibrada e filtrada)
  Cabeçalho (enviado uma vez no início):
    #H;t_ms;pitch;roll;ax_g;ay_g;az_g;temp_c;\n
  Mensagens informativas (nunca mudam o estado do dashboard):
    #M;TEXTO;\n          ex.: #M;WHO_AM_I_70; no boot

  Comandos (PC -> Arduino) e a resposta de cada um (ACK, "#<CMD>;<STATUS>;"):
    #Z\n   zera pitch/roll na posição atual (média de ~0,12 s, a placa deve estar parada)   ->  #Z;OK;
    outro comando (inclusive os antigos #C e #R)                                              ->  #M;COMANDO_DESCONHECIDO;

  CALIBRAÇÃO DO ACELERÔMETRO (uma vez por módulo; guardada na EEPROM). O dashboard faz isso na tela de
  Configurações ("Calibrar acelerômetro"); os mesmos comandos funcionam num terminal serial (pio device monitor)
    Com a placa PARADA e o eixo indicado apontando PARA CIMA (U) ou PARA BAIXO (D), envie:
      #KXU #KXD #KYU #KYD #KZU #KZD     cada um faz a média de ~0,5 s e responde  #K<eixo><sentido>;OK;
    Ao completar as 6 posições calcula  offset = (cima+baixo)/2  e  ganho = (cima-baixo)/2, grava e envia
      #M;CALIBRACAO_SALVA;  e  #K;OFFSET;ox;oy;oz;SCALE;sx;sy;sz;
    Se algum ganho ficar fora de 0,5 a 1,5 descarta tudo:  #M;CALIBRACAO_INVALIDA_REPITA_AS_POSICOES;
    #KP -> #KP;OK; e a linha acima com a calibração em uso      #KR -> #KR;OK;, volta ao padrão (offset 0, ganho 1)
*/


#include <Arduino.h>
#include <Wire.h>
#include <EEPROM.h>

#define MPU_ADDR 0x68

const uint8_t REG_CONFIG = 0x1A;
const uint8_t REG_ACCEL_CONFIG = 0x1C;
const uint8_t REG_ACCEL_CONFIG2 = 0x1D;  // só existe no MPU-6500; inofensivo no 6050
const uint8_t REG_ACCEL_XOUT_H = 0x3B;
const uint8_t REG_PWR_MGMT_1 = 0x6B;
const uint8_t REG_WHO_AM_I = 0x75;
const int WHO_MPU6050 = 0x68;

const unsigned long SAMPLE_US = 10000UL;  // 100 Hz
const float TAU_S = 0.2f;                 // constante de tempo do passa-baixa do vetor de aceleração
const int CAPTURE_SAMPLES = 100;          // ~0,5 s por posição de calibração (o dashboard dá "sem sinal" após 1 s)
const int ZERO_SAMPLES = 25;              // ~0,12 s de média ao zerar (#Z)

struct Calib {
  uint16_t magic;
  float offset[3];  // leitura = ganho * g + offset
  float scale[3];
};
const uint16_t CALIB_MAGIC = 0xA6C1;
Calib calib;

uint8_t capturedMask = 0;  // bit 0..5: XU XD YU YD ZU ZD
float capUp[3], capDown[3];

bool isMpu6050 = false;    // muda só a fórmula da temperatura
float accF[3];             // aceleração calibrada e filtrada (g)
bool filterReady = false;
float pitchZero = 0, rollZero = 0;
unsigned long lastUs = 0;

char rxBuf[16];
uint8_t rxLen = 0;
bool rxOverflow = false;

// ---------- saída ----------

// Linha informativa: #M;TEXTO;
void msg(const __FlashStringHelper *text) {
  Serial.print(F("#M;"));
  Serial.print(text);
  Serial.print(';');
  Serial.print('\n');
}

// Resposta de comando (ACK): o texto já traz "#<CMD>;<STATUS>;"
void reply(const __FlashStringHelper *text) {
  Serial.print(text);
  Serial.print('\n');
}

void printCalib() {
  Serial.print(F("#K;OFFSET;"));
  for (int i = 0; i < 3; i++) { Serial.print(calib.offset[i], 4); Serial.print(';'); }
  Serial.print(F("SCALE;"));
  for (int i = 0; i < 3; i++) { Serial.print(calib.scale[i], 4); Serial.print(';'); }
  Serial.print('\n');
}

// ---------- calibração (EEPROM) ----------

void resetCalib() {
  calib.magic = CALIB_MAGIC;
  for (int i = 0; i < 3; i++) { calib.offset[i] = 0; calib.scale[i] = 1; }
}

void loadCalib() {
  EEPROM.get(0, calib);
  if (calib.magic != CALIB_MAGIC) resetCalib();
}

void saveCalib() {
  EEPROM.put(0, calib);
}

// ---------- sensor (I2C direto) ----------

bool writeReg(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

int readReg(uint8_t reg) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return -1;
  if (Wire.requestFrom((uint8_t)MPU_ADDR, (uint8_t)1) != 1) return -1;
  return Wire.read();
}

// Lê o acelerômetro (g, bruto) e a temperatura (°C) numa única transação (6 + 2 bytes).
bool readSensor(float acc[3], float *temp) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(REG_ACCEL_XOUT_H);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((uint8_t)MPU_ADDR, (uint8_t)8) != 8) return false;
  int16_t v[4];
  for (int i = 0; i < 4; i++) {
    uint8_t hi = Wire.read();
    uint8_t lo = Wire.read();
    v[i] = (int16_t)((hi << 8) | lo);
  }
  for (int i = 0; i < 3; i++) acc[i] = v[i] / 16384.0f;  // ±2 g
  *temp = isMpu6050 ? v[3] / 340.0f + 36.53f : v[3] / 333.87f + 21.0f;
  return true;
}

void calibrated(const float raw[3], float out[3]) {
  for (int i = 0; i < 3; i++) out[i] = (raw[i] - calib.offset[i]) / calib.scale[i];
}

// ---------- ângulos ----------

float anglePitch(const float a[3]) {
  return atan2(-a[0], sqrt(a[1] * a[1] + a[2] * a[2])) * 180.0f / PI;
}

float angleRoll(const float a[3]) {
  return atan2(a[1], a[2]) * 180.0f / PI;
}

// ---------- comandos ----------

// Média bruta de CAPTURE_SAMPLES leituras do eixo `axis`; false se o sensor falhar.
bool captureAxis(int axis, float *average) {
  float sum = 0;
  for (int n = 0; n < CAPTURE_SAMPLES; n++) {
    float acc[3], temp;
    if (!readSensor(acc, &temp)) return false;
    sum += acc[axis];
    delay(5);
  }
  *average = sum / CAPTURE_SAMPLES;
  return true;
}

// Média calibrada de ZERO_SAMPLES leituras: a pose de agora, sem o atraso do passa-baixa.
bool captureCurrentPose(float out[3]) {
  float sum[3] = {0, 0, 0};
  for (int n = 0; n < ZERO_SAMPLES; n++) {
    float raw[3], a[3], temp;
    if (!readSensor(raw, &temp)) return false;
    calibrated(raw, a);
    for (int i = 0; i < 3; i++) sum[i] += a[i];
    delay(5);
  }
  for (int i = 0; i < 3; i++) out[i] = sum[i] / ZERO_SAMPLES;
  return true;
}

void finishCalibrationIfComplete() {
  if (capturedMask != 0x3F) return;
  float offset[3], scale[3];
  for (int i = 0; i < 3; i++) {
    offset[i] = (capUp[i] + capDown[i]) / 2.0f;
    scale[i] = (capUp[i] - capDown[i]) / 2.0f;
    if (scale[i] < 0.5f || scale[i] > 1.5f) {
      msg(F("CALIBRACAO_INVALIDA_REPITA_AS_POSICOES"));
      capturedMask = 0;
      return;
    }
  }
  for (int i = 0; i < 3; i++) { calib.offset[i] = offset[i]; calib.scale[i] = scale[i]; }
  saveCalib();
  capturedMask = 0;
  filterReady = false;
  msg(F("CALIBRACAO_SALVA"));
  printCalib();
}

// "#K" + eixo (X|Y|Z) + sentido (U|D): captura uma posição. "#KP" mostra a calibração, "#KR" a restaura.
void handleCalibrationCommand(const char *cmd) {
  if (strcmp(cmd, "#KP") == 0) {
    reply(F("#KP;OK;"));
    printCalib();
    return;
  }
  if (strcmp(cmd, "#KR") == 0) {
    resetCalib();
    saveCalib();
    capturedMask = 0;
    filterReady = false;
    reply(F("#KR;OK;"));
    printCalib();
    return;
  }
  const char *axes = "XYZ";
  const char *axisPtr = strlen(cmd) == 4 ? strchr(axes, cmd[2]) : NULL;
  if (axisPtr == NULL || (cmd[3] != 'U' && cmd[3] != 'D')) {
    msg(F("COMANDO_DESCONHECIDO"));
    return;
  }
  int axis = axisPtr - axes;
  bool up = cmd[3] == 'U';
  float average;
  if (!captureAxis(axis, &average)) {
    msg(F("FALHA_DE_LEITURA_DO_SENSOR"));
    return;
  }
  (up ? capUp : capDown)[axis] = average;
  capturedMask |= (1 << (axis * 2 + (up ? 0 : 1)));
  Serial.print(cmd);
  Serial.print(F(";OK;"));
  Serial.print('\n');
  filterReady = false;
  finishCalibrationIfComplete();
}

void processCommand(const char *cmd) {
  if (strcmp(cmd, "#Z") == 0) {
    float pose[3];
    if (!captureCurrentPose(pose)) {
      msg(F("FALHA_DE_LEITURA_DO_SENSOR"));
    } else {
      for (int i = 0; i < 3; i++) accF[i] = pose[i];  // o filtro parte da pose zerada: saída 0 na hora
      filterReady = true;
      pitchZero = anglePitch(accF);
      rollZero = angleRoll(accF);
      reply(F("#Z;OK;"));
    }
  } else if (cmd[0] == '#' && cmd[1] == 'K') {
    handleCalibrationCommand(cmd);
  } else {
    msg(F("COMANDO_DESCONHECIDO"));
  }
  lastUs = micros();  // os comandos que capturam amostras bloqueiam o laço por um tempo
}

// Monta a linha recebida e executa ao chegar '\n'
void handleCommands() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (!rxOverflow) {
        rxBuf[rxLen] = '\0';
        processCommand(rxBuf);
      }
      rxLen = 0;
      rxOverflow = false;
    } else if (rxLen < sizeof(rxBuf) - 1) {
      rxBuf[rxLen++] = toupper(c);
    } else {
      rxOverflow = true;  // linha longa demais: descarta até o '\n'
    }
  }
}

// ---------- setup / loop ----------

void setup() {
  Serial.begin(115200);
  Wire.begin();
  Wire.setClock(400000);

  int who = readReg(REG_WHO_AM_I);
  if (who < 0) {
    msg(F("MPU_NAO_RESPONDEU_CONFIRA_LIGACAO_E_ENDERECO_0X68_0X69"));
    while (true) { delay(1000); }
  }
  isMpu6050 = (who == WHO_MPU6050);
  Serial.print(F("#M;WHO_AM_I_"));
  Serial.print(who, HEX);
  Serial.print(';');
  Serial.print('\n');

  writeReg(REG_PWR_MGMT_1, 0x01);     // acorda, relógio = PLL do giroscópio X
  delay(100);
  writeReg(REG_CONFIG, 0x03);         // passa-baixa digital ~44 Hz
  writeReg(REG_ACCEL_CONFIG, 0x00);   // ±2 g
  writeReg(REG_ACCEL_CONFIG2, 0x03);  // MPU-6500: passa-baixa do acelerômetro ~44 Hz
  delay(100);
  loadCalib();

  msg(F("ENVIE_Z_COM_O_CARRO_EM_SOLO_PLANO_PARA_ZERAR"));
  Serial.print(F("#H;t_ms;pitch;roll;ax_g;ay_g;az_g;temp_c;"));
  Serial.print('\n');
  lastUs = micros();
}

void loop() {
  handleCommands();

  unsigned long now = micros();
  if (now - lastUs < SAMPLE_US) return;
  float dt = (now - lastUs) / 1e6f;
  lastUs = now;

  float raw[3], temp;
  if (!readSensor(raw, &temp)) return;

  float a[3];
  calibrated(raw, a);
  if (!filterReady) {
    for (int i = 0; i < 3; i++) accF[i] = a[i];
    filterReady = true;
  } else {
    float k = dt / (TAU_S + dt);
    for (int i = 0; i < 3; i++) accF[i] += k * (a[i] - accF[i]);
  }

  Serial.print(F("#D;"));
  Serial.print(millis());                          Serial.print(';');
  Serial.print(anglePitch(accF) - pitchZero, 2);   Serial.print(';');
  Serial.print(angleRoll(accF) - rollZero, 2);     Serial.print(';');
  Serial.print(accF[0], 3);                        Serial.print(';');
  Serial.print(accF[1], 3);                        Serial.print(';');
  Serial.print(accF[2], 3);                        Serial.print(';');
  Serial.print(temp, 1);                           Serial.print(';');
  Serial.print('\n');
}
