/**
 * Input Validation Utilities
 * Provides client-side validation for form inputs
 *
 * Migrated to TypeScript: January 18, 2026
 * Safe: Pure utility functions, no side effects
 */

export interface ValidationResult {
  valid: boolean;
  error: string | null;
}

export type ValidatorFunction = (value: any, allValues?: Record<string, any>) => boolean;

export interface ValidationRule {
  validator: ValidatorFunction | string;
  message: string;
  params?: any[];
}

export const validators = {
  // Number validations
  isNumber: (value: any): boolean => {
    const num = parseFloat(value);
    return !isNaN(num) && isFinite(num);
  },

  isPositive: (value: any): boolean => {
    return validators.isNumber(value) && parseFloat(value) > 0;
  },

  isNonNegative: (value: any): boolean => {
    return validators.isNumber(value) && parseFloat(value) >= 0;
  },

  inRange: (value: any, min: number, max: number): boolean => {
    if (!validators.isNumber(value)) return false;
    const num = parseFloat(value);
    return num >= min && num <= max;
  },

  // String validations
  isNotEmpty: (value: any): boolean => {
    return value !== null && value !== undefined && value.toString().trim().length > 0;
  },

  minLength: (value: any, length: number): boolean => {
    return value && value.toString().length >= length;
  },

  maxLength: (value: any, length: number): boolean => {
    return value && value.toString().length <= length;
  },

  // Pattern validations
  isEmail: (value: string): boolean => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(value);
  },

  isUrl: (value: string): boolean => {
    try {
      new URL(value);
      return true;
    } catch {
      return false;
    }
  },

  // Trading-specific validations
  isValidPrice: (value: any): boolean => {
    return validators.isPositive(value);
  },

  isValidQuantity: (value: any): boolean => {
    return validators.isPositive(value);
  },

  isValidPercentage: (value: any): boolean => {
    return validators.inRange(value, 0, 100);
  },

  isValidLeverage: (value: any, maxLeverage: number = 125): boolean => {
    return validators.inRange(value, 1, maxLeverage);
  },

  isValidSymbol: (value: string): boolean => {
    // Basic symbol validation (e.g., BTCUSDT)
    return /^[A-Z0-9]{4,12}$/.test(value);
  },
};

/**
 * Validation rule builder
 */
export const createValidator = (rules: ValidationRule[]) => {
  return (value: any, allValues: Record<string, any> = {}): ValidationResult => {
    for (const rule of rules) {
      const { validator, message, params = [] } = rule;

      let isValid = false;

      if (typeof validator === 'function') {
        isValid = validator(value, allValues);
      } else if (
        typeof validator === 'string' &&
        validators[validator as keyof typeof validators]
      ) {
        isValid = (validators[validator as keyof typeof validators] as any)(value, ...params);
      }

      if (!isValid) {
        return { valid: false, error: message };
      }
    }

    return { valid: true, error: null };
  };
};

/**
 * Common validation rules
 */
export const validationRules = {
  required: {
    validator: validators.isNotEmpty,
    message: 'This field is required',
  },

  positiveNumber: {
    validator: validators.isPositive,
    message: 'Must be a positive number',
  },

  nonNegativeNumber: {
    validator: validators.isNonNegative,
    message: 'Must be a non-negative number',
  },

  percentage: {
    validator: validators.isValidPercentage,
    message: 'Must be between 0 and 100',
  },

  leverage: (max: number = 125): ValidationRule => ({
    validator: (value: any) => validators.isValidLeverage(value, max),
    message: `Leverage must be between 1 and ${max}`,
  }),

  minValue: (min: number): ValidationRule => ({
    validator: (value: any) => validators.isNumber(value) && parseFloat(value) >= min,
    message: `Must be at least ${min}`,
  }),

  maxValue: (max: number): ValidationRule => ({
    validator: (value: any) => validators.isNumber(value) && parseFloat(value) <= max,
    message: `Must be at most ${max}`,
  }),

  range: (min: number, max: number): ValidationRule => ({
    validator: (value: any) => validators.inRange(value, min, max),
    message: `Must be between ${min} and ${max}`,
  }),

  email: {
    validator: validators.isEmail,
    message: 'Invalid email address',
  },

  url: {
    validator: validators.isUrl,
    message: 'Invalid URL',
  },

  symbol: {
    validator: validators.isValidSymbol,
    message: 'Invalid trading symbol (e.g., BTCUSDT)',
  },
};

/**
 * Validate form data
 */
export const validateForm = (
  data: Record<string, any>,
  schema: Record<string, ValidationRule[]>
): { isValid: boolean; errors: Record<string, string> } => {
  const errors: Record<string, string> = {};
  let isValid = true;

  for (const [field, rules] of Object.entries(schema)) {
    const validator = createValidator(rules);
    const result = validator(data[field], data);

    if (!result.valid) {
      errors[field] = result.error!;
      isValid = false;
    }
  }

  return { isValid, errors };
};

/**
 * Sanitize input values
 */
export const sanitizers = {
  trimString: (value: any): any => {
    return typeof value === 'string' ? value.trim() : value;
  },

  toNumber: (value: any): number | null => {
    const num = parseFloat(value);
    return isNaN(num) ? null : num;
  },

  toUpperCase: (value: any): any => {
    return typeof value === 'string' ? value.toUpperCase() : value;
  },

  toLowerCase: (value: any): any => {
    return typeof value === 'string' ? value.toLowerCase() : value;
  },

  removeWhitespace: (value: any): any => {
    return typeof value === 'string' ? value.replace(/\s/g, '') : value;
  },

  limitDecimals: (value: any, decimals: number = 2): any => {
    const num = parseFloat(value);
    if (isNaN(num)) return value;
    return parseFloat(num.toFixed(decimals));
  },
};

export default {
  validators,
  createValidator,
  validationRules,
  validateForm,
  sanitizers,
};
