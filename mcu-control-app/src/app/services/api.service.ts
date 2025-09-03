import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError, BehaviorSubject, timer } from 'rxjs';
import { catchError, retry, tap, switchMap, map } from 'rxjs/operators';
import {
  StatusResponse,
  LedControlRequest,
  LedControlResponse,
  LampStatusResponse,
  LampStatusRequest,
  NetworkInfo,
  ApiError,
  DeviceType
} from '../models/api.models';

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private http = inject(HttpClient);
  
  // Base URL - can be configured for different environments
  private baseUrl = '';
  
  // Device type detection
  private deviceTypeSubject = new BehaviorSubject<DeviceType>(DeviceType.MCU);
  public deviceType$ = this.deviceTypeSubject.asObservable();
  
  // Connection status
  private connectionStatusSubject = new BehaviorSubject<boolean>(false);
  public connectionStatus$ = this.connectionStatusSubject.asObservable();
  
  // Auto-refresh status
  private autoRefreshSubject = new BehaviorSubject<boolean>(false);
  public autoRefresh$ = this.autoRefreshSubject.asObservable();

  constructor() {
    // Don't auto-detect device type - wait for user connection
    console.log('API Service initialized. Ready for connection.');

    // Start auto-refresh if enabled
    this.autoRefresh$.pipe(
      switchMap(enabled => enabled ? timer(0, 2000) : [])
    ).subscribe(() => {
      if (this.autoRefreshSubject.value && this.isConnected()) {
        this.getStatus().subscribe();
      }
    });
  }

  /**
   * Set the base URL for API calls
   */
  setBaseUrl(url: string): void {
    this.baseUrl = url.endsWith('/') ? url.slice(0, -1) : url;
  }

  /**
   * Get current device status (LEDs and buttons)
   */
  getStatus(): Observable<StatusResponse> {
    return this.http.get<StatusResponse>(`${this.baseUrl}/api/status`).pipe(
      tap(() => {
        console.log('getStatus success - setting connection status to true');
        this.connectionStatusSubject.next(true);
      }),
      catchError(this.handleError.bind(this))
    );
  }

  /**
   * Control LED state and brightness
   */
  controlLed(request: LedControlRequest): Observable<LedControlResponse> {
    return this.http.post<LedControlResponse>(`${this.baseUrl}/api/leds`, request).pipe(
      retry(1),
      catchError(this.handleError.bind(this))
    );
  }

  /**
   * Get lamp status
   */
  getLampStatus(): Observable<LampStatusResponse> {
    return this.http.get<LampStatusResponse>(`${this.baseUrl}/api/lamp`).pipe(
      catchError(this.handleError.bind(this))
    );
  }

  /**
   * Set lamp configuration
   */
  setLampStatus(request: LampStatusRequest): Observable<any> {
    // Wrap the request in the expected format
    const wrappedRequest = {
      request: request.nearInfraredStatus ? {
        nearInfraredStatus: request.nearInfraredStatus,
        ...(request.redLightStatus && { redLightStatus: request.redLightStatus })
      } : request
    };

    return this.http.post<any>(`${this.baseUrl}/api/lamp`, wrappedRequest).pipe(
      retry(1),
      catchError(this.handleError.bind(this))
    );
  }

  /**
   * Get network information
   */
  getNetworkInfo(): Observable<NetworkInfo> {
    return this.http.get<NetworkInfo>(`${this.baseUrl}/api/network`).pipe(
      catchError(this.handleError.bind(this))
    );
  }

  /**
   * Detect device type based on network info
   */
  private detectDeviceType(): void {
    this.getNetworkInfo().subscribe({
      next: (info) => {
        if (info.device_type === 'ESP32 CYD') {
          this.deviceTypeSubject.next(DeviceType.ESP32_CYD);
        } else {
          this.deviceTypeSubject.next(DeviceType.MCU);
        }
      },
      error: () => {
        // Default to MCU if detection fails
        this.deviceTypeSubject.next(DeviceType.MCU);
      }
    });
  }

  /**
   * Toggle auto-refresh
   */
  toggleAutoRefresh(): void {
    this.autoRefreshSubject.next(!this.autoRefreshSubject.value);
  }

  /**
   * Set auto-refresh state
   */
  setAutoRefresh(enabled: boolean): void {
    this.autoRefreshSubject.next(enabled);
  }

  /**
   * Test connection to the device
   */
  testConnection(): Observable<boolean> {
    return this.getStatus().pipe(
      tap(() => this.connectionStatusSubject.next(true)),
      map(() => true),
      catchError(() => {
        this.connectionStatusSubject.next(false);
        return throwError(() => new Error('Connection failed'));
      })
    );
  }

  /**
   * Handle HTTP errors
   */
  private handleError(error: HttpErrorResponse): Observable<never> {
    console.log('handleError called - setting connection status to false');
    this.connectionStatusSubject.next(false);
    
    let errorMessage = 'An unknown error occurred';
    
    if (error.error instanceof ErrorEvent) {
      // Client-side error
      errorMessage = `Client Error: ${error.error.message}`;
    } else {
      // Server-side error
      if (error.status === 0) {
        errorMessage = 'Unable to connect to device. Please check the IP address and network connection.';
      } else if (error.error && typeof error.error === 'object' && 'error' in error.error) {
        errorMessage = `Server Error: ${error.error.error}`;
      } else {
        errorMessage = `Server Error ${error.status}: ${error.message}`;
      }
    }

    console.error('API Error:', errorMessage, error);
    return throwError(() => new Error(errorMessage));
  }

  /**
   * Get current device type
   */
  getCurrentDeviceType(): DeviceType {
    return this.deviceTypeSubject.value;
  }

  /**
   * Get current connection status
   */
  isConnected(): boolean {
    return this.connectionStatusSubject.value;
  }

  /**
   * Get LED color name - supports dynamic LED counts
   */
  getLedColorName(ledNumber: number): string {
    if (this.getCurrentDeviceType() === DeviceType.ESP32_CYD) {
      // ESP32 CYD specific naming for RGB LEDs
      switch (ledNumber) {
        case 1: return 'Red';
        case 2: return 'Green';
        case 3: return 'Blue';
        default: return `LED ${ledNumber}`;
      }
    }
    // Generic MCU device - support any number of LEDs
    return `LED ${ledNumber}`;
  }

  /**
   * Get LED color CSS class - supports dynamic LED counts
   */
  getLedColorClass(ledNumber: number): string {
    if (this.getCurrentDeviceType() === DeviceType.ESP32_CYD) {
      // ESP32 CYD specific colors for RGB LEDs
      switch (ledNumber) {
        case 1: return 'led-red';
        case 2: return 'led-green';
        case 3: return 'led-blue';
        default: return 'led-default';
      }
    }
    // Generic MCU device - cycle through colors for visual distinction
    const colors = ['led-red', 'led-green', 'led-blue', 'led-orange', 'led-purple', 'led-cyan'];
    const colorIndex = (ledNumber - 1) % colors.length;
    return colors[colorIndex];
  }
}
