/*
  Inclinômetro com MPU-6500 usando a biblioteca MPU6500_WE (Wolfgang Ewald)
  Instalar: Arduino IDE -> Gerenciar Bibliotecas -> "MPU6500_WE"

  Ligações (Nano/Uno): VCC->5V (módulo com regulador) ou 3V3, GND->GND,
                       SDA->A4, SCL->A5
  Endereço I2C: 0x68 (AD0 em GND) ou 0x69 (AD0 em VCC)

  Orientação assumida: X = frente do carro, Y = esquerda, Z = para cima
    pitch (+) = nariz para baixo, roll (+) = lado direito para baixo

  PROTOCOLO SERIAL (115200 baud, linhas terminadas em '\n', colunas separadas por ';')

  Comandos (PC -> Arduino):
    #Z\n  zera pitch/roll na posição atual (compensa o ângulo do painel)
    #R\n  remove o zero
    #C\n  recalibra o giroscópio (carro parado!)

  Saída (Arduino -> PC), 100 Hz:
    #D;t_ms;pitch;roll;ax_g;ay_g;az_g;gx_dps;gy_dps;gz_dps;temp_c;\n
  Cabeçalho (enviado uma vez no início):
    #H;t_ms;pitch;roll;ax_g;ay_g;az_g;gx_dps;gy_dps;gz_dps;temp_c;\n
  Mensagens de status:
    #M;texto;\n

  Obs.: NAO uso autoOffsets() da biblioteca, pois ela assume o módulo
  nivelado e apagaria a inclinação do painel. O giroscópio é calibrado
  aqui e o zero é feito pelo comando #Z.
*/

#include <Wire.h>
#include <MPU6500_WE.h>

#define MPU_ADDR 0x68
MPU6500_WE mpu = MPU6500_WE(MPU_ADDR);

const unsigned long SAMPLE_US = 10000UL;  // 100 Hz
const float ALPHA = 0.98f;                // peso do giroscópio no filtro
const int CALIB_SAMPLES = 500;

float gBiasX = 0, gBiasY = 0, gBiasZ = 0;
float pitch = 0, roll = 0;                // ângulos filtrados (sem zero)
float pitchZero = 0, rollZero = 0;
unsigned long lastUs = 0;

// Buffer de recepção de comandos
char rxBuf[16];
uint8_t rxLen = 0;
bool rxOverflow = false;

void msg(const __FlashStringHelper *text) {
  Serial.print(F("#M;"));
  Serial.print(text);
  Serial.print(';');
  Serial.print('\n');
}

float accelPitch(float ax, float ay, float az) {
  return atan2(-ax, sqrt(ay * ay + az * az)) * 180.0f / PI;
}

float accelRoll(float ay, float az) {
  return atan2(ay, az) * 180.0f / PI;
}

void calibrateGyro() {
  msg(F("Calibrando giroscopio: mantenha o carro parado"));
  float sx = 0, sy = 0, sz = 0;
  for (int i = 0; i < CALIB_SAMPLES; i++) {
    xyzFloat g = mpu.getGyrValues();
    sx += g.x; sy += g.y; sz += g.z;
    delay(3);
  }
  gBiasX = sx / CALIB_SAMPLES;
  gBiasY = sy / CALIB_SAMPLES;
  gBiasZ = sz / CALIB_SAMPLES;

  // Inicializa os ângulos direto pelo acelerômetro
  xyzFloat a = mpu.getGValues();
  pitch = accelPitch(a.x, a.y, a.z);
  roll = accelRoll(a.y, a.z);
  msg(F("Calibracao ok"));
}

void processCommand(const char *cmd) {
  if (strcmp(cmd, "#Z") == 0) {
    pitchZero = pitch;
    rollZero = roll;
    msg(F("Zero definido"));
  } else if (strcmp(cmd, "#R") == 0) {
    pitchZero = 0;
    rollZero = 0;
    msg(F("Zero removido"));
  } else if (strcmp(cmd, "#C") == 0) {
    calibrateGyro();
    lastUs = micros();
  } else {
    msg(F("Comando desconhecido"));
  }
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

void setup() {
  Serial.begin(115200);
  Wire.begin();
  Wire.setClock(400000);

  if (!mpu.init()) {
    msg(F("MPU6500 nao respondeu. Confira ligacao e endereco 0x68/0x69"));
    while (true) { delay(1000); }
  }

  mpu.setGyrRange(MPU6500_GYRO_RANGE_500);
  mpu.setAccRange(MPU6500_ACC_RANGE_2G);

  // Filtros passa-baixa internos (~41-44 Hz) para cortar vibração
  mpu.enableGyrDLPF();
  mpu.setGyrDLPF(MPU6500_DLPF_3);
  mpu.enableAccDLPF(true);
  mpu.setAccDLPF(MPU6500_DLPF_3);
  delay(200);

  calibrateGyro();
  msg(F("Envie #Z com o carro em solo plano para zerar"));
  Serial.print(F("#H;t_ms;pitch;roll;ax_g;ay_g;az_g;gx_dps;gy_dps;gz_dps;temp_c;"));
  Serial.print('\n');
  lastUs = micros();
}

void loop() {
  handleCommands();

  unsigned long now = micros();
  if (now - lastUs < SAMPLE_US) return;
  float dt = (now - lastUs) / 1e6f;
  lastUs = now;

  xyzFloat a = mpu.getGValues();
  xyzFloat g = mpu.getGyrValues();
  float temp = mpu.getTemperature();

  float gx = g.x - gBiasX;
  float gy = g.y - gBiasY;
  float gz = g.z - gBiasZ;

  // Integra o giroscópio
  pitch += gy * dt;
  roll += gx * dt;

  // Corrige com o acelerômetro só quando a leitura é ~1 g
  // (em frenagem/curva/arrancada o acelerômetro não mede só a gravidade)
  float mag = sqrt(a.x * a.x + a.y * a.y + a.z * a.z);
  if (fabs(mag - 1.0f) < 0.15f) {
    pitch = ALPHA * pitch + (1.0f - ALPHA) * accelPitch(a.x, a.y, a.z);
    roll = ALPHA * roll + (1.0f - ALPHA) * accelRoll(a.y, a.z);
  }

  Serial.print(F("#D;"));
  Serial.print(millis());              Serial.print(';');
  Serial.print(pitch - pitchZero, 2);  Serial.print(';');
  Serial.print(roll - rollZero, 2);    Serial.print(';');
  Serial.print(a.x, 3);                Serial.print(';');
  Serial.print(a.y, 3);                Serial.print(';');
  Serial.print(a.z, 3);                Serial.print(';');
  Serial.print(gx, 2);                 Serial.print(';');
  Serial.print(gy, 2);                 Serial.print(';');
  Serial.print(gz, 2);                 Serial.print(';');
  Serial.print(temp, 1);               Serial.print(';');
  Serial.print('\n');
}
