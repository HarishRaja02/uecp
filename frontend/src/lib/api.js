const API_HOST = (typeof window !== 'undefined' && window.location.hostname) || 'localhost'
const isDevStandalone = typeof window !== 'undefined' && (window.location.port === '5174' || window.location.port === '5173')
export const API_BASE = import.meta.env.VITE_API_URL || (isDevStandalone ? `http://${API_HOST}:8001/api/v1` : '/api/v1')
const BASE = API_BASE
let accessToken = null
let refreshPromise=null
async function refreshAccessToken(){
 if(!refreshPromise) refreshPromise=fetch(BASE+'/auth/refresh',{method:'POST',credentials:'include'}).then(async response=>{if(!response.ok)throw new Error('Session expired');const value=await response.json();accessToken=value.access_token;return value}).finally(()=>{refreshPromise=null})
 return refreshPromise
}
export function clearAccessToken(){accessToken=null}
export async function api(path,options={}){
 const headers=new Headers(options.headers||{}); if(options.body&&!headers.has('Content-Type')) headers.set('Content-Type','application/json'); if(accessToken) headers.set('Authorization',`Bearer ${accessToken}`)
 let r=await fetch(BASE+path,{...options,headers,credentials:'include'})
 if(r.status===401&&path!=='/auth/refresh'){try{await refreshAccessToken();headers.set('Authorization',`Bearer ${accessToken}`);r=await fetch(BASE+path,{...options,headers,credentials:'include'})}catch(error){clearAccessToken();throw error}}
 const body=await r.json().catch(()=>({})); if(!r.ok) throw new Error(body.message||body.error||'Request failed'); return body
}
export async function login(email,password){const x=await api('/auth/login',{method:'POST',body:JSON.stringify({email,password})});accessToken=x.access_token;return x}
export async function refresh(){const x=await api('/auth/refresh',{method:'POST'});accessToken=x.access_token;return x}
export async function logout(){try{await api('/auth/logout',{method:'POST'})}finally{clearAccessToken()}}
