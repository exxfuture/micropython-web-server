// API Models for MCU Control Application

export interface LedStatus {
  [key: string]: boolean; // Dynamic LED count - can be 1, 2, 3, 4, 5, 6, etc.
}

export interface LedBrightness {
  [key: string]: number; // Dynamic LED brightness - matches LED count
}

export interface ButtonStatus {
  1?: number;
  2?: number;
  boot?: number; // For ESP32 CYD
}

export interface StatusResponse {
  leds: LedStatus;
  led_brightness?: LedBrightness; // Optional for ESP32 CYD
  buttons: ButtonStatus;
}

export interface LedControlRequest {
  led: number; // 1-3
  value: boolean;
  brightness?: number; // 0-100, optional for ESP32 CYD
}

export interface LedControlResponse {
  ok: boolean;
  led: number;
  value: boolean;
  brightness?: number;
}

export interface LampStatus {
  power: string; // "ON", "OFF", "PAUSE"
  mode: string; // "STATIC", "WAVE", "PULSE"
  brightness: number; // 0-100
  speed: number; // 1-100 seconds
  timer: number; // seconds
  elapsedTime: number; // seconds
}

export interface LampStatusResponse {
  nearInfraredStatus: LampStatus;
  redLightStatus: LampStatus;
}

export interface LampStatusRequest {
  request?: {
    nearInfraredStatus: LampStatus;
    redLightStatus?: LampStatus;
  };
  nearInfraredStatus?: LampStatus;
  redLightStatus?: LampStatus;
}

export interface NetworkInfo {
  configured_mode: string; // "WiFi" or "Ethernet"
  ip_address: string;
  subnet_mask: string;
  gateway: string;
  dns: string;
  connected: boolean;
  web_storage: string; // "SD Card" or "Flash Memory"
  web_root: string;
  device_type?: string; // "ESP32 CYD" for ESP32 version
  wifi_ssid?: string;
  wifi_connected?: boolean;
  wifi_signal_strength?: string;
}

export interface ApiError {
  error: string;
}

// Device Types
export enum DeviceType {
  MCU = 'MCU',
  ESP32_CYD = 'ESP32_CYD'
}

// LED Colors for ESP32 CYD
export enum LedColor {
  RED = 1,
  GREEN = 2,
  BLUE = 3
}

// Power States
export enum PowerState {
  ON = 'ON',
  OFF = 'OFF',
  PAUSE = 'PAUSE'
}

// Lamp Modes
export enum LampMode {
  STATIC = 'STATIC',
  WAVE = 'WAVE',
  PULSE = 'PULSE'
}

// Network Modes
export enum NetworkMode {
  WIFI = 'WiFi',
  ETHERNET = 'Ethernet'
}

// Storage Types
export enum StorageType {
  SD_CARD = 'SD Card',
  FLASH_MEMORY = 'Flash Memory'
}
