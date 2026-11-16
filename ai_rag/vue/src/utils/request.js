import axios from "axios";
import {ElMessage} from "element-plus";
import router from "@/router/index.js";

const request = axios.create({
    // BaseURL read from VITE_BASE_URL of .env. development, developing environment point to http://localhost:9090,
    // Write.post('/login') on this page would be a request for http://localhost:9090/login
    baseURL: import.meta.env.VITE_BASE_URL,
    // Backstage interface timed out, AI-related interfaces took longer. This is 30 seconds.
    withCredentials: true,
    timeout: 30000
})

// Interceptor
// You can handle requests from the moment they are sent.
request.interceptors.request.use(config => {
    config.headers['Content-Type'] = 'application/json;charset=utf-8';
    let user = JSON.parse(localStorage.getItem("xm-user") || '{}')
    config.headers['token'] = user.token || ''
    return config
}, error => {
    return Promise.reject(error)
});

// interceptor
// The result can be treated uniformly after the interface response
request.interceptors.response.use(
    response => {
        let res = response.data;
        // If returned file
        if (response.config.responseType === 'blob') {
            return res
        }
        // Give a hint when permission is not checked
        if (res.code === '401') {
            ElMessage.error(res.msg)
            router.push('/login')
        }
        // String data returned by compatible service end
        if (typeof res === 'string') {
            res = res ? JSON.parse(res) : res
        }
        return res;
    },
    error => {
        if (error.config?.quiet) return Promise.reject(error)
        const status = error.response?.status
        if (!status) {
            ElMessage.error('Could not reach the server. Try again in a moment.')
        } else if (status === 404) {
            ElMessage.error('Request Interface Not Found')
        } else if (status === 500) {
            ElMessage.error('System Exception, Please Check Backend Console Error')
        } else {
            console.error(error.message)
        }
        return Promise.reject(error)
    }
)

export default request
