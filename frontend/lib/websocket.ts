/**
 * WebSocket manager for real-time updates from the Vigil backend.
 * Handles connection lifecycle, reconnection, and event distribution.
 */

type EventCallback = (data: unknown) => void;

interface WebSocketManagerConfig {
  url?: string;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

const DEFAULT_CONFIG: Required<WebSocketManagerConfig> = {
  url: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws',
  reconnectInterval: 3000,
  maxReconnectAttempts: 5,
};

export class WebSocketManager {
  private ws: WebSocket | null = null;
  private config: Required<WebSocketManagerConfig>;
  private listeners: Map<string, Set<EventCallback>> = new Map();
  private reconnectAttempts = 0;
  private isConnecting = false;
  private isManuallyClosed = false;

  constructor(config?: WebSocketManagerConfig) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * Establish WebSocket connection.
   */
  connect(): void {
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
      return;
    }

    this.isManuallyClosed = false;
    this.isConnecting = true;

    try {
      this.ws = new WebSocket(this.config.url);

      this.ws.onopen = () => {
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.emit('connected', null);
      };

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          const eventType = data.type ?? 'message';
          this.emit(eventType, data);
        } catch {
          this.emit('message', event.data);
        }
      };

      this.ws.onerror = (error: Event) => {
        this.isConnecting = false;
        this.emit('error', error);
      };

      this.ws.onclose = () => {
        this.isConnecting = false;
        this.emit('disconnected', null);

        if (!this.isManuallyClosed && this.reconnectAttempts < this.config.maxReconnectAttempts) {
          this.reconnectAttempts++;
          setTimeout(() => this.connect(), this.config.reconnectInterval);
        }
      };
    } catch (error) {
      this.isConnecting = false;
      this.emit('error', error);
    }
  }

  /**
   * Subscribe to a specific event type.
   */
  on(event: string, callback: EventCallback): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);
  }

  /**
   * Unsubscribe from a specific event type.
   */
  off(event: string, callback: EventCallback): void {
    this.listeners.get(event)?.delete(callback);
  }

  /**
   * Send a message to the server.
   */
  send(data: unknown): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      console.warn('WebSocket is not connected');
    }
  }

  /**
   * Close the WebSocket connection.
   */
  disconnect(): void {
    this.isManuallyClosed = true;
    this.ws?.close();
    this.ws = null;
  }

  /**
   * Check if the connection is open.
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Emit an event to all registered listeners.
   */
  private emit(event: string, data: unknown): void {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.forEach((callback) => callback(data));
    }
  }
}

// Singleton instance for global use
let wsManager: WebSocketManager | null = null;

export function getWebSocketManager(): WebSocketManager {
  if (!wsManager) {
    wsManager = new WebSocketManager();
  }
  return wsManager;
}
