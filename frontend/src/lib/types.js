/**
 * @typedef {Object} PartResult
 * @property {string} ps_number
 * @property {string} name
 * @property {number|null} price
 * @property {string|null} stock_status
 * @property {string|null} image_url
 * @property {string|null} product_url
 * @property {string|null} brand
 */

/**
 * @typedef {Object} CompatibilityResult
 * @property {boolean} compatible
 * @property {string} reason
 * @property {string|null} ps_number
 * @property {string|null} part_name
 */

/**
 * @typedef {Object} CartSummary
 * @property {Array} items
 * @property {number} total
 * @property {number} count
 */

/**
 * @typedef {Object} ChatResponse
 * @property {string} session_id
 * @property {string} text
 * @property {PartResult[]} [parts]
 * @property {string[]} [installation_steps]
 * @property {CompatibilityResult} [compatibility]
 * @property {Object} [cart_update]
 * @property {boolean} [out_of_scope]
 */
