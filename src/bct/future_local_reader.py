"""Cost-zero CPU quick reading, exclusively through a local llama.cpp process.

No hosted-model fallback, context truncation, invented token counts or scores.
The setup owner verifies official weight hashes and the pinned server build.
"""
import hashlib
import json
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .future_reader import INSTRUCTIONS, SCHEMA, validate_output


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('local reader redirect rejected')


class LocalCPUQuickReader:
    def __init__(self, receipt, *, port=8080, timeout=180, requester=None):
        if isinstance(port,bool) or not isinstance(port,int) or not 1<=port<=65535:
            raise ValueError('invalid local reader port')
        if not 0<timeout<=600:raise ValueError('invalid local reader timeout')
        self.receipt=receipt;self.base='http://127.0.0.1:'+str(port)
        self.timeout=timeout;self.requester=requester or self._request

    def preflight(self):
        r=self.receipt
        if (r.get('provider')!='local-cpu' or r.get('weights_verified') is not True
                or r.get('build_verified') is not True or r.get('api_cost_usd')!=0
                or r.get('license')!='Apache-2.0' or not r.get('files')
                or not r.get('alias') or not isinstance(r.get('context_tokens'),int)
                or r.get('context_tokens',0)<=r.get('max_output_tokens',1000)):
            return 'LOCAL_READER_NOT_VERIFIED'
        return None

    def input_characters(self,payload):
        return len(INSTRUCTIONS)+len(json.dumps(payload,ensure_ascii=False))+150

    def _request(self,path,value):
        if path not in ('/tokenize','/completion'):raise ValueError('local endpoint rejected')
        req=Request(self.base+path,data=json.dumps(value,ensure_ascii=False).encode(),
                    headers={'Content-Type':'application/json'})
        with build_opener(NoRedirect()).open(req,timeout=self.timeout) as response:
            raw=response.read(1_000_001)
        if len(raw)>1_000_000:raise ValueError('local reader response too large')
        return json.loads(raw)

    def __call__(self,payload):
        if self.preflight():raise RuntimeError('LOCAL_READER_NOT_VERIFIED')
        body=payload['body']
        if hashlib.sha256(body.encode()).hexdigest()!=payload['body_sha256']:
            raise ValueError('local reader source hash mismatch')
        if payload['expected_read_end']!=len(body):raise ValueError('local reader body extent mismatch')
        # The pinned Qwen2.5 ChatML format is tokenized once, then the exact
        # token array is submitted. Numeric prompts do not add a hidden BOS.
        prompt='<|im_start|>system\n'+INSTRUCTIONS+'<|im_end|>\n<|im_start|>user\n'+json.dumps(payload,ensure_ascii=False)+'<|im_end|>\n<|im_start|>assistant\n'
        tokenized=self.requester('/tokenize',{'content':prompt,'add_special':False,'parse_special':True})
        tokens=tokenized.get('tokens')
        if not isinstance(tokens,list) or not tokens or any(type(t) is not int or t<0 for t in tokens):
            raise ValueError('invalid local prompt tokenization')
        maximum=self.receipt['max_output_tokens']
        if len(tokens)+maximum>self.receipt['context_tokens']:
            raise ValueError('local reader context budget exceeded')
        result=self.requester('/completion',{'prompt':tokens,'json_schema':SCHEMA,
            'n_predict':maximum,'temperature':0,'seed':0,'stream':False,'cache_prompt':False})
        if (result.get('truncated') is not False or result.get('stop_type') not in ('eos','word')
                or result.get('tokens_evaluated')!=len(tokens)
                or result.get('model')!=self.receipt['alias']):
            raise ValueError('local reader inference receipt incomplete or mismatched')
        output=result.get('timings',{}).get('predicted_n')
        if type(output) is not int or output<=0:raise ValueError('invalid local output token count')
        decision=validate_output(json.loads(result['content']),payload)
        return {'review':decision,'usage':{'input_tokens':len(tokens),'output_tokens':output},
                'provider':'local-cpu','model':self.receipt['model'],
                'model_revision':self.receipt['revision'],'api_cost_usd':0,
                'inference_receipt':{'tokens_evaluated':len(tokens),'truncated':False,
                    'stop_type':result['stop_type'],'llama_cpp_sha':self.receipt['llama_cpp_sha']}}
