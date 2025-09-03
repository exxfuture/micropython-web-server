import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatSliderModule } from '@angular/material/slider';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBarModule, MatSnackBar } from '@angular/material/snack-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatChipsModule } from '@angular/material/chips';
import { MatDividerModule } from '@angular/material/divider';
import { MatExpansionModule } from '@angular/material/expansion';
import { Subject, takeUntil, interval } from 'rxjs';

import { ApiService } from './services/api.service';
import {
  StatusResponse,
  LedControlRequest,
  LampStatusRequest,
  NetworkInfo,
  DeviceType,
  LampStatus,
  PowerState,
  LampMode
} from './models/api.models';

@Component({
  selector: 'app-root',
  imports: [
    CommonModule,
    FormsModule,
    MatToolbarModule,
    MatCardModule,
    MatButtonModule,
    MatSlideToggleModule,
    MatSliderModule,
    MatInputModule,
    MatFormFieldModule,
    MatIconModule,
    MatSnackBarModule,
    MatProgressSpinnerModule,
    MatChipsModule,
    MatDividerModule,
    MatExpansionModule
  ],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App implements OnInit, OnDestroy {
  private destroy$ = new Subject<void>();
  private apiService = inject(ApiService);
  private snackBar = inject(MatSnackBar);

  title = 'MCU Control Application';

  // Connection settings
  deviceIp = '192.168.1.100';
  isConnected = false;
  isConnecting = false;
  autoRefresh = false;

  // Device info
  deviceType = DeviceType.MCU;
  networkInfo: NetworkInfo | null = null;

  // Status data
  status: StatusResponse | null = null;
  lampStatus: any = null;

  // LED control - dynamic arrays based on device response
  ledStates: boolean[] = [];
  ledBrightness: number[] = [];
  ledCount = 0;
  ledNumbers: number[] = []; // Actual LED numbers from API (e.g., [1, 2, 3, 4, 5, 6])

  // Lamp control
  nearInfraredConfig: LampStatus = {
    power: PowerState.OFF,
    mode: LampMode.STATIC,
    brightness: 50,
    speed: 20,
    timer: 10,
    elapsedTime: 0
  };

  redLightConfig: LampStatus = {
    power: PowerState.OFF,
    mode: LampMode.STATIC,
    brightness: 50,
    speed: 20,
    timer: 10,
    elapsedTime: 0
  };

  // Enums for template
  PowerState = PowerState;
  LampMode = LampMode;
  DeviceType = DeviceType;

  ngOnInit() {
    // Subscribe to device type changes
    this.apiService.deviceType$.pipe(
      takeUntil(this.destroy$)
    ).subscribe(type => {
      this.deviceType = type;
    });

    // Subscribe to connection status
    this.apiService.connectionStatus$.pipe(
      takeUntil(this.destroy$)
    ).subscribe(connected => {
      console.log('Connection status changed:', connected);
      this.isConnected = connected;
      // Only reset isConnecting if we're disconnecting
      if (!connected) {
        this.isConnecting = false;
      }
      console.log('Component isConnected:', this.isConnected);
    });

    // Subscribe to auto-refresh status
    this.apiService.autoRefresh$.pipe(
      takeUntil(this.destroy$)
    ).subscribe(enabled => {
      this.autoRefresh = enabled;
    });

    // Don't auto-connect - wait for user to click connect button
    console.log('Application initialized. Click "Connect" to connect to device.');
  }

  ngOnDestroy() {
    this.destroy$.next();
    this.destroy$.complete();
  }

  connect() {
    if (!this.deviceIp) {
      this.showError('Please enter a valid IP address');
      return;
    }

    console.log('Starting connection to:', this.deviceIp);
    this.isConnecting = true;
    this.apiService.setBaseUrl(`http://${this.deviceIp}`);

    this.apiService.testConnection().subscribe({
      next: () => {
        console.log('testConnection success callback');
        this.isConnecting = false;
        this.showSuccess('Connected successfully!');
        console.log('About to detect device type and load data');
        // Detect device type after successful connection
        this.detectDeviceType();
        this.loadAllData();
        console.log('Connection process completed');
      },
      error: (error) => {
        console.error('testConnection error callback:', error);
        this.isConnecting = false;
        this.showError(`Connection failed: ${error.message}`);
      }
    });
  }

  disconnect() {
    this.isConnected = false;
    this.apiService.setAutoRefresh(false);
    this.status = null;
    this.lampStatus = null;
    this.networkInfo = null;

    // Reset device type and LED data
    this.deviceType = DeviceType.MCU;
    this.ledStates = [];
    this.ledBrightness = [];
    this.ledCount = 0;
    this.ledNumbers = [];

    console.log('Disconnected from device');
  }

  toggleAutoRefresh() {
    this.apiService.toggleAutoRefresh();
  }

  loadAllData() {
    this.loadStatus();
    this.loadLampStatus();
    this.loadNetworkInfo();
  }

  loadStatus() {
    console.log('Loading status...');
    this.apiService.getStatus().subscribe({
      next: (status) => {
        console.log('Status received:', status);
        this.status = status;
        this.updateLedStatesFromStatus(status);
      },
      error: (error) => {
        console.error('Failed to load status:', error);
        this.showError(`Failed to load status: ${error.message}`);
      }
    });
  }

  private updateLedStatesFromStatus(status: StatusResponse) {
    console.log('Updating LED states from status:', status);

    // Get LED numbers from the response
    const ledNumbers = Object.keys(status.leds).map(key => parseInt(key)).sort((a, b) => a - b);
    this.ledCount = ledNumbers.length;
    this.ledNumbers = ledNumbers;

    console.log('LED numbers found:', ledNumbers);
    console.log('LED count:', this.ledCount);

    // Initialize arrays if needed
    if (this.ledStates.length !== this.ledCount) {
      this.ledStates = new Array(this.ledCount).fill(false);
      this.ledBrightness = new Array(this.ledCount).fill(50);
      console.log('Initialized LED arrays:', { ledStates: this.ledStates, ledBrightness: this.ledBrightness });
    }

    // Update LED states based on response
    ledNumbers.forEach((ledNumber, index) => {
      this.ledStates[index] = status.leds[ledNumber.toString()];

      // Update brightness if available
      if (status.led_brightness && status.led_brightness[ledNumber.toString()] !== undefined) {
        this.ledBrightness[index] = status.led_brightness[ledNumber.toString()];
      }
    });

    console.log(`Final LED states:`, this.ledStates);
    console.log(`Final LED brightness:`, this.ledBrightness);
    console.log(`Detected ${this.ledCount} LEDs:`, ledNumbers);
  }

  loadLampStatus() {
    console.log('Loading lamp status...');
    this.apiService.getLampStatus().subscribe({
      next: (lampStatus) => {
        console.log('Lamp status received:', lampStatus);
        this.lampStatus = lampStatus;
        this.nearInfraredConfig = { ...lampStatus.nearInfraredStatus };
        this.redLightConfig = { ...lampStatus.redLightStatus };
      },
      error: (error) => {
        console.error('Failed to load lamp status:', error);
        this.showError(`Failed to load lamp status: ${error.message}`);
      }
    });
  }

  loadNetworkInfo() {
    this.apiService.getNetworkInfo().subscribe({
      next: (info) => {
        this.networkInfo = info;
      },
      error: (error) => {
        console.warn('Failed to load network info:', error.message);
      }
    });
  }

  detectDeviceType() {
    console.log('Detecting device type...');
    this.apiService.getNetworkInfo().subscribe({
      next: (info) => {
        console.log('Network info received:', info);
        if (info.device_type === 'ESP32 CYD') {
          this.deviceType = DeviceType.ESP32_CYD;
        } else {
          this.deviceType = DeviceType.MCU;
        }
        console.log(`Device type detected: ${this.deviceType}`);
      },
      error: (error) => {
        // Default to MCU if detection fails
        console.error('Device type detection failed:', error);
        this.deviceType = DeviceType.MCU;
        console.log('Device type detection failed, defaulting to MCU');
      }
    });
  }

  // LED Control Methods
  toggleLed(ledIndex: number) {
    if (ledIndex >= this.ledNumbers.length) {
      this.showError('Invalid LED index');
      return;
    }

    const ledNumber = this.ledNumbers[ledIndex];
    const newState = !this.ledStates[ledIndex];

    const request: LedControlRequest = {
      led: ledNumber,
      value: newState,
      brightness: this.ledBrightness[ledIndex]
    };

    this.apiService.controlLed(request).subscribe({
      next: (response) => {
        this.ledStates[ledIndex] = response.value;
        if (response.brightness !== undefined) {
          this.ledBrightness[ledIndex] = response.brightness;
        }
        this.showSuccess(`${this.apiService.getLedColorName(ledNumber)} LED ${newState ? 'ON' : 'OFF'}`);
      },
      error: (error) => {
        this.showError(`Failed to control LED: ${error.message}`);
      }
    });
  }

  updateLedBrightness(ledIndex: number, event: any) {
    if (ledIndex >= this.ledNumbers.length) {
      this.showError('Invalid LED index');
      return;
    }

    const brightness = typeof event === 'number' ? event : event.target?.value || 0;
    const ledNumber = this.ledNumbers[ledIndex];

    const request: LedControlRequest = {
      led: ledNumber,
      value: brightness > 0,
      brightness: brightness
    };

    this.apiService.controlLed(request).subscribe({
      next: (response) => {
        this.ledStates[ledIndex] = response.value;
        if (response.brightness !== undefined) {
          this.ledBrightness[ledIndex] = response.brightness;
        }
      },
      error: (error) => {
        this.showError(`Failed to update LED brightness: ${error.message}`);
      }
    });
  }

  // Lamp Control Methods
  updateNearInfraredLamp() {
    const request: LampStatusRequest = {
      nearInfraredStatus: this.nearInfraredConfig
    };

    this.apiService.setLampStatus(request).subscribe({
      next: () => {
        this.showSuccess('Near Infrared lamp updated');
        this.loadLampStatus();
      },
      error: (error) => {
        this.showError(`Failed to update Near Infrared lamp: ${error.message}`);
      }
    });
  }

  updateRedLightLamp() {
    const request: LampStatusRequest = {
      redLightStatus: this.redLightConfig
    };

    this.apiService.setLampStatus(request).subscribe({
      next: () => {
        this.showSuccess('Red Light lamp updated');
        this.loadLampStatus();
      },
      error: (error) => {
        this.showError(`Failed to update Red Light lamp: ${error.message}`);
      }
    });
  }

  toggleNearInfraredPower() {
    this.nearInfraredConfig.power = this.nearInfraredConfig.power === PowerState.ON ? PowerState.OFF : PowerState.ON;
    this.updateNearInfraredLamp();
  }

  toggleRedLightPower() {
    this.redLightConfig.power = this.redLightConfig.power === PowerState.ON ? PowerState.OFF : PowerState.ON;
    this.updateRedLightLamp();
  }

  // Utility Methods
  getLedColorName(ledIndex: number): string {
    if (ledIndex >= this.ledNumbers.length) return `LED ${ledIndex + 1}`;
    const ledNumber = this.ledNumbers[ledIndex];
    return this.apiService.getLedColorName(ledNumber);
  }

  getLedColorClass(ledIndex: number): string {
    if (ledIndex >= this.ledNumbers.length) return 'led-default';
    const ledNumber = this.ledNumbers[ledIndex];
    return this.apiService.getLedColorClass(ledNumber);
  }

  private showSuccess(message: string) {
    this.snackBar.open(message, 'Close', {
      duration: 3000,
      panelClass: ['success-snackbar']
    });
  }

  private showError(message: string) {
    this.snackBar.open(message, 'Close', {
      duration: 5000,
      panelClass: ['error-snackbar']
    });
  }

  getButtonStatusText(value: number | undefined): string {
    if (value === undefined) return 'Unknown';
    return value === 0 ? 'Pressed' : 'Released';
  }

  getPowerStateIcon(power: string): string {
    switch (power) {
      case PowerState.ON: return 'power';
      case PowerState.OFF: return 'power_off';
      case PowerState.PAUSE: return 'pause';
      default: return 'help';
    }
  }

  getModeIcon(mode: string): string {
    switch (mode) {
      case LampMode.STATIC: return 'lightbulb';
      case LampMode.WAVE: return 'waves';
      case LampMode.PULSE: return 'flash_on';
      default: return 'help';
    }
  }
}
