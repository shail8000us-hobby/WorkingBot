/**
 * Sound Manager - Centralized audio playback for trade notifications
 * 
 * Features:
 * - Preloads sound effects
 * - Manages audio playback with volume control
 * - Handles browser autoplay restrictions gracefully
 * - Multiple sound types for different actions
 * - User preferences stored in localStorage
 */

class SoundManager {
  constructor() {
    // Load preferences from localStorage
    const savedPrefs = this._loadPreferences();
    
    this.enabled = savedPrefs.enabled;
    this.volume = savedPrefs.volume;
    this.soundTypes = {
      buy: savedPrefs.soundTypes.buy,
      sell: savedPrefs.soundTypes.sell,
      close: savedPrefs.soundTypes.close,
      profit: savedPrefs.soundTypes.profit,
      loss: savedPrefs.soundTypes.loss,
    };
    this.sounds = {};
    this.initialized = false;
    this.audioContext = null;
    this.buffers = {};
  }
  
  /**
   * Load preferences from localStorage
   */
  _loadPreferences() {
    try {
      const saved = localStorage.getItem('soundPreferences');
      if (saved) {
        return JSON.parse(saved);
      }
    } catch (e) {
      console.warn('Failed to load sound preferences:', e);
    }
    
    // Default preferences
    return {
      enabled: true,
      volume: 0.5,
      soundTypes: {
        buy: 'chime',
        sell: 'chime',
        close: 'chime',
        profit: 'success',
        loss: 'gentle',
      }
    };
  }
  
  /**
   * Save preferences to localStorage
   */
  _savePreferences() {
    try {
      const prefs = {
        enabled: this.enabled,
        volume: this.volume,
        soundTypes: this.soundTypes,
      };
      localStorage.setItem('soundPreferences', JSON.stringify(prefs));
    } catch (e) {
      console.warn('Failed to save sound preferences:', e);
    }
  }

  /**
   * Initialize sound manager and preload sounds
   */
  initialize() {
    if (this.initialized) return;
    
    try {
      // Create AudioContext
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      
      // Generate programmatic sounds (always available)
      this.buffers.chime = this._generateChimeSound();
      this.buffers.success = this._generateSuccessSound();
      this.buffers.gentle = this._generateGentleSound();
      this.buffers.alert = this._generateAlertSound();
      
      // Load macOS system sounds
      this._loadSystemSounds();
      
      this.initialized = true;
      console.log('✅ Sound Manager initialized with', Object.keys(this.buffers).length, 'generated sounds + system sounds loading');
    } catch (error) {
      console.warn('Sound Manager initialization failed:', error);
      this.enabled = false;
    }
  }
  
  /**
   * Load macOS system sounds from public/sounds directory
   */
  _loadSystemSounds() {
    const systemSounds = [
      'Basso', 'Blow', 'Bottle', 'Frog', 'Funk', 'Glass', 
      'Hero', 'Morse', 'Ping', 'Pop', 'Purr', 'Sosumi', 
      'Submarine', 'Tink'
    ];
    
    systemSounds.forEach(name => {
      try {
        // Create audio element on demand (avoid autoplay restrictions)
        this.sounds[name.toLowerCase()] = {
          name: name,
          loaded: false,
          create: () => {
            const audio = new Audio(`${process.env.PUBLIC_URL || ''}/sounds/${name}.aiff`);
            audio.volume = this.volume;
            audio.preload = 'auto';
            return audio;
          }
        };
      } catch (error) {
        console.warn(`Failed to prepare system sound: ${name}`, error);
      }
    });
  }

  /**
   * Generate soft chime sound (C major chord)
   */
  _generateChimeSound() {
    const sampleRate = this.audioContext.sampleRate;
    const duration = 0.4;
    const numSamples = sampleRate * duration;
    const buffer = this.audioContext.createBuffer(1, numSamples, sampleRate);
    const data = buffer.getChannelData(0);
    
    const frequencies = [523.25, 659.25, 783.99]; // C5, E5, G5
    
    for (let i = 0; i < numSamples; i++) {
      const t = i / sampleRate;
      const fadeIn = Math.min(1, t * 10);
      const fadeOut = Math.max(0, 1 - (t / duration) * 2);
      const envelope = fadeIn * fadeOut * 0.15;
      
      let sample = 0;
      frequencies.forEach(freq => {
        sample += Math.sin(2 * Math.PI * freq * t) / frequencies.length;
      });
      data[i] = sample * envelope;
    }
    
    return buffer;
  }
  
  /**
   * Generate success sound (ascending notes)
   */
  _generateSuccessSound() {
    const sampleRate = this.audioContext.sampleRate;
    const duration = 0.3;
    const numSamples = sampleRate * duration;
    const buffer = this.audioContext.createBuffer(1, numSamples, sampleRate);
    const data = buffer.getChannelData(0);
    
    const frequencies = [523.25, 659.25]; // C5, E5 (happy interval)
    
    for (let i = 0; i < numSamples; i++) {
      const t = i / sampleRate;
      const progress = t / duration;
      const freq = frequencies[0] + (frequencies[1] - frequencies[0]) * progress;
      const envelope = Math.sin(Math.PI * progress) * 0.12;
      
      data[i] = Math.sin(2 * Math.PI * freq * t) * envelope;
    }
    
    return buffer;
  }
  
  /**
   * Generate gentle sound (single soft tone)
   */
  _generateGentleSound() {
    const sampleRate = this.audioContext.sampleRate;
    const duration = 0.25;
    const numSamples = sampleRate * duration;
    const buffer = this.audioContext.createBuffer(1, numSamples, sampleRate);
    const data = buffer.getChannelData(0);
    
    const frequency = 440; // A4 (calm tone)
    
    for (let i = 0; i < numSamples; i++) {
      const t = i / sampleRate;
      const envelope = Math.exp(-t * 8) * 0.1; // Quick decay
      data[i] = Math.sin(2 * Math.PI * frequency * t) * envelope;
    }
    
    return buffer;
  }
  
  /**
   * Generate alert sound (higher pitch)
   */
  _generateAlertSound() {
    const sampleRate = this.audioContext.sampleRate;
    const duration = 0.2;
    const numSamples = sampleRate * duration;
    const buffer = this.audioContext.createBuffer(1, numSamples, sampleRate);
    const data = buffer.getChannelData(0);
    
    const frequency = 880; // A5 (attention-grabbing)
    
    for (let i = 0; i < numSamples; i++) {
      const t = i / sampleRate;
      const envelope = Math.sin(Math.PI * t / duration) * 0.15;
      data[i] = Math.sin(2 * Math.PI * frequency * t) * envelope;
    }
    
    return buffer;
  }

  /**
   * Play sound for specific action
   */
  _playSound(soundType) {
    if (!this.enabled || !this.initialized) {
      return;
    }

    try {
      // Check if it's a generated sound (Web Audio API)
      const buffer = this.buffers[soundType];
      if (buffer) {
        const source = this.audioContext.createBufferSource();
        const gainNode = this.audioContext.createGain();
        
        source.buffer = buffer;
        gainNode.gain.value = this.volume;
        
        source.connect(gainNode);
        gainNode.connect(this.audioContext.destination);
        
        source.start(0);
        return;
      }
      
      // Check if it's a system sound (Audio element)
      const audio = this.sounds[soundType];
      if (audio) {
        try {
          // Create fresh audio instance for system sounds
          const audioElement = audio.create ? audio.create() : audio;
          audioElement.volume = this.volume;
          audioElement.currentTime = 0;
          audioElement.play().catch(err => {
            console.warn('Failed to play system sound:', err);
          });
        } catch (err) {
          console.warn('Error playing system sound:', err);
        }
        return;
      }
      
      console.warn('Sound type not found:', soundType);
    } catch (error) {
      console.warn('Failed to play sound:', error);
    }
  }
  
  /**
   * Play trade filled sound (legacy method - uses default chime)
   */
  playTradeFilled() {
    this._playSound('chime');
  }
  
  /**
   * Play buy order sound
   */
  playBuy() {
    const soundType = this.soundTypes.buy || 'chime';
    this._playSound(soundType);
  }
  
  /**
   * Play sell order sound
   */
  playSell() {
    const soundType = this.soundTypes.sell || 'chime';
    this._playSound(soundType);
  }
  
  /**
   * Play position close sound
   */
  playClose() {
    const soundType = this.soundTypes.close || 'chime';
    this._playSound(soundType);
  }
  
  /**
   * Play profit sound
   */
  playProfit() {
    const soundType = this.soundTypes.profit || 'success';
    this._playSound(soundType);
  }
  
  /**
   * Play loss sound
   */
  playLoss() {
    const soundType = this.soundTypes.loss || 'gentle';
    this._playSound(soundType);
  }

  /**
   * Set volume (0.0 to 1.0)
   */
  setVolume(volume) {
    this.volume = Math.max(0, Math.min(1, volume));
    this._savePreferences();
  }

  /**
   * Enable/disable sounds
   */
  setEnabled(enabled) {
    this.enabled = enabled;
    this._savePreferences();
  }

  /**
   * Check if sounds are enabled
   */
  isEnabled() {
    return this.enabled;
  }
  
  /**
   * Set sound type for specific action
   */
  setSoundType(action, soundType) {
    if (this.soundTypes.hasOwnProperty(action)) {
      this.soundTypes[action] = soundType;
      this._savePreferences();
    }
  }
  
  /**
   * Get current sound type for action
   */
  getSoundType(action) {
    return this.soundTypes[action] || 'chime';
  }
  
  /**
   * Get all available sound types
   */
  getAvailableSounds() {
    const generated = Object.keys(this.buffers);
    const system = Object.keys(this.sounds);
    return [...generated, ...system];
  }
  
  /**
   * Preview a sound type
   */
  previewSound(soundType) {
    this._playSound(soundType);
  }

  /**
   * Generic play method for compatibility
   * @param {string} soundName - Sound name: 'orderPlaced', 'orderFailed', 'success', 'error', etc.
   */
  play(soundName) {
    const soundMap = {
      'orderPlaced': 'chime',
      'orderFilled': 'success',
      'orderFailed': 'error',
      'success': 'success',
      'error': 'error',
      'warning': 'gentle',
      'buy': 'chime',
      'sell': 'chime'
    };
    const soundType = soundMap[soundName] || soundName || 'chime';
    this._playSound(soundType);
  }
}

// Singleton instance
const soundManager = new SoundManager();

// Auto-initialize on user interaction (to handle browser autoplay restrictions)
if (typeof window !== 'undefined') {
  const initOnInteraction = () => {
    soundManager.initialize();
    document.removeEventListener('click', initOnInteraction);
    document.removeEventListener('keydown', initOnInteraction);
  };
  
  document.addEventListener('click', initOnInteraction, { once: true });
  document.addEventListener('keydown', initOnInteraction, { once: true });
}

export default soundManager;
