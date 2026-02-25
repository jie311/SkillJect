/**
 * test_suite_template.js
 *
 * 用于生成 API 测试套件的模板。此模板为各种 API 端点创建综合测试用例提供结构。
 *
 * @example
 * // 示例用法（替换占位符后）：
 * const testSuite = require('./test_suite_template');
 *
 * const config = {
 *   baseURL: 'https://api.example.com',
 *   endpoint: '/users',
 *   method: 'GET',
 *   description: 'Retrieve all users'
 * };
 *
 * const testCase = testSuite(config);
 *
 * describe(config.description, () => {
 *   it('should return a 200 OK status', async () => {
 *     const response = await testCase.request();
 *     expect(response.status).toBe(200);
 *   });
 *   // 在此添加更多测试用例...
 * });
 */

/**
 * 根据提供的配置生成测试套件。
 *
 * @param {object} config - 测试套件的配置对象。
 * @param {string} config.baseURL - API 的基础 URL。
 * @param {string} config.endpoint - 要测试的 API 端点。
 * @param {string} config.method - 要使用的 HTTP 方法（GET、POST、PUT、DELETE 等）。
 * @param {string} config.description - 测试用例的描述。
 * @param {object} [config.headers] - 要包含在请求中的可选请求头。
 * @param {object} [config.body] - 可选的请求体。
 * @param {string} [config.authenticationType] - 可选的认证类型（例如：'Bearer'、'OAuth'、'API Key'）。
 * @param {string} [config.authenticationToken] - 可选的认证令牌或 API 密钥。
 * @returns {object} 包含请求函数的对象。
 */
module.exports = (config) => {
  const axios = require('axios'); // 如果需要，考虑将 axios 设为可配置的依赖项

  /**
   * 根据配置执行 API 请求。
   *
   * @async
   * @function request
   * @returns {Promise<object>} 解析为 API 响应的 Promise。
   * @throws {Error} 如果请求失败。
   */
  async function request() {
    try {
      const requestConfig = {
        method: config.method,
        url: config.baseURL + config.endpoint,
        headers: config.headers || {},
        data: config.body || null, // 对 POST/PUT 请求使用 data，对 GET 请求使用 params
        // params: config.method === 'GET' ? config.body : null // 备选：对 GET 请求使用 params
      };

      // 认证处理
      if (config.authenticationType === 'Bearer' && config.authenticationToken) {
        requestConfig.headers.Authorization = `Bearer ${config.authenticationToken}`;
      } else if (config.authenticationType === 'API Key' && config.authenticationToken) {
        // 示例 API Key 请求头 -- 根据 API 要求进行调整
        requestConfig.headers['X-API-Key'] = config.authenticationToken;
      } // 根据需要添加更多认证类型

      const response = await axios(requestConfig);
      return response;
    } catch (error) {
      // 适当处理错误（例如：记录、重新抛出或返回自定义错误对象）
      console.error(`请求失败，针对 ${config.description}：`, error.message);
      throw error; // 重新抛出错误供测试处理
    }
  }

  return {
    request,

    // 如果需要，在此添加更多辅助函数（例如：用于数据验证）
    validateResponseSchema: (response, schema) => {
      // 占位符：使用像 Joi 或 Ajv 这样的库实现模式验证逻辑
      // 示例：
      // const validationResult = schema.validate(response.data);
      // if (validationResult.error) {
      //   throw new Error(`模式验证失败：${validationResult.error.message}`);
      // }
    },
    extractDataFromResponse: (response, path) => {
        // 占位符：使用像 lodash.get 这样的库实现从响应中提取数据的逻辑
        // 示例：
        // return _.get(response.data, path);
    }
  };
};
