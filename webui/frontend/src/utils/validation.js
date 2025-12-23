/**
 * Input Validation Utilities
 * Provides client-side validation for form inputs
 */

export const validators = {
  // Number validations
  isNumber: (value) => {
    const num = parseFloat(value);
    return !isNaN(num) && isFinite(num);
  },

  isPositive: (value) => {
    return validators.isNumber(value) && parseFloat(value) > 0;
  },

  isNonNegative: (value) => {
    return validators.isNumber(value) && parseFloat(value) >= 0;
  },

  inRange: (value, min, max) => {
    if (!validators.isNumber(value)) return false;
    const num = parseFloat(value);
    return num >= min && num <= max;
  },

  // String validations
  isNotEmpty: (value) => {
    return value !== null && value !== undefined && value.toString().trim().length > 0;
  },

  minLength: (value, length) => {
    return value && value.toString().length >= length;
  },

  maxLength: (value, length) => {
    return value && value.toString().length <= length;
  },

  // Pattern validations
  isEmail: (value) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(value);
  },

  isUrl: (value) => {
    try {
      new URL(value);
      return true;
    } catch {
      return false;
    }
  },

  // Trading-specific validations
  isValidPrice: (value) => {
    return validators.isPositive(value);
  },

  isValidQuantity: (value) => {
    return validators.isPositive(value);
  },

  isValidPercentage: (value) => {
    return validators.inRange(value, 0, 100);
  },

  isValidLeverage: (value, maxLeverage = 125) => {
    return validators.inRange(value, 1, maxLeverage);
  },

  isValidSymbol: (value) => {
    // Basic symbol validation (e.g., BTCUSDT)
    return /^[A-Z0-9]{4,12}$/.test(value);
  }
};

/**
 * Validation rule builder
 */
export const createValidator = (rules) => {
  return (value, allValues = {}) => {
    for (const rule of rules) {
      const { validator, message, params = [] } = rule;
      
      let isValid = false;
      
      if (typeof validator === 'function') {
        isValid = validator(value, allValues);
      } else if (typeof validator === 'string' && validators[validator]) {
        isValid = validators[validator](value, ...params);
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
    message: 'This field is required'
  },

  positiveNumber: {
    validator: validators.isPositive,
    message: 'Must be a positive number'
  },

  nonNegativeNumber: {
    validator: validators.isNonNegative,
    message: 'Must be a non-negative number'
  },

  percentage: {
    validator: validators.isValidPercentage,
    message: 'Must be between 0 and 100'
  },

  leverage: (max = 125) => ({
    validator: validators.isValidLeverage,
    params: [max],
    message: `Leverage must be between 1 and ${max}`
  }),

  minValue: (min) => ({
    validator: (value) => validators.isNumber(value) && parseFloat(value) >= min,
    message: `Must be at least ${min}`
  }),

  maxValue: (max) => ({
    validator: (value) => validators.isNumber(value) && parseFloat(value) <= max,
    message: `Must be at most ${max}`
  }),

  range: (min, max) => ({
    validator: (value) => validators.inRange(value, min, max),
    message: `Must be between ${min} and ${max}`
  }),

  email: {
    validator: validators.isEmail,
    message: 'Invalid email address'
  },

  url: {
    validator: validators.isUrl,
    message: 'Invalid URL'
  },

  symbol: {
    validator: validators.isValidSymbol,
    message: 'Invalid trading symbol (e.g., BTCUSDT)'
  }
};

/**
 * Validate form data
 */
export const validateForm = (data, schema) => {
  const errors = {};
  let isValid = true;

  for (const [field, rules] of Object.entries(schema)) {
    const validator = createValidator(rules);
    const result = validator(data[field], data);
    
    if (!result.valid) {
      errors[field] = result.error;
      isValid = false;
    }
  }

  return { isValid, errors };
};

/**
 * Sanitize input values
 */
export const sanitizers = {
  trimString: (value) => {
    return typeof value === 'string' ? value.trim() : value;
  },

  toNumber: (value) => {
    const num = parseFloat(value);
    return isNaN(num) ? null : num;
  },

  toUpperCase: (value) => {
    return typeof value === 'string' ? value.toUpperCase() : value;
  },

  toLowerCase: (value) => {
    return typeof value === 'string' ? value.toLowerCase() : value;
  },

  removeWhitespace: (value) => {
    return typeof value === 'string' ? value.replace(/\s/g, '') : value;
  },

  limitDecimals: (value, decimals = 2) => {
    const num = parseFloat(value);
    if (isNaN(num)) return value;
    return parseFloat(num.toFixed(decimals));
  }
};

export default {
  validators,
  createValidator,
  validationRules,
  validateForm,
  sanitizers
};
