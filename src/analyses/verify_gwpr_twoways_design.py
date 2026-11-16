#!/usr/bin/env python3
"""Audit local two-way FE semantics using a small deterministic synthetic panel.

This is algorithm validation, not an additional empirical model. No GWPR
package is installed or executed. R's existing plm and lm provide references.
"""
from pathlib import Path
import json
import subprocess

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/estimation-framework-planning/gwpr-twoways'


def weighted_within(values, weights):
    demeaned = values-values.mean(axis=1,keepdims=True)
    period = np.einsum('i,itp->tp',weights,demeaned)/weights.sum()
    return demeaned-period[None,:,:]


def fit(values, weights, compatible=False):
    if compatible:
        z=values-values.mean(axis=1,keepdims=True)-values.mean(axis=0,keepdims=True)+values.mean(axis=(0,1),keepdims=True)
    else:
        z=weighted_within(values,weights)
    x=z[:,:,1:].reshape(-1,2); y=z[:,:,0].reshape(-1)
    root=np.repeat(np.sqrt(weights),values.shape[1])
    return np.linalg.lstsq(x*root[:,None],y*root,rcond=None)[0]


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(20261009)
    n,t=12,4
    x=rng.normal(size=(n,t,2))
    x[:,:,0]+=np.linspace(-2,2,n)[:,None]*np.array([-1,0,0.5,1])[None,:]
    y=0.7*x[:,:,0]-0.4*x[:,:,1]+rng.normal(size=(n,1))*3+np.array([4,-2,1,-3])[None,:]+rng.normal(size=(n,t))*0.3
    values=np.concatenate([y[:,:,None],x],axis=2)
    weights=np.array([1,.9,.7,.5,.3,.2,.1,.03,0,0,0,0])
    frame=pd.DataFrame({'id':np.repeat(np.arange(1,n+1),t),'time':np.tile(np.arange(1,t+1),n),
        'y':y.reshape(-1),'x1':x[:,:,0].reshape(-1),'x2':x[:,:,1].reshape(-1),'weight':np.repeat(weights,t)})
    frame.to_csv(OUT/'synthetic_panel.csv',index=False)
    r_source='''args <- commandArgs(trailingOnly=TRUE)
d <- read.csv(args[1])
weighted_dummy <- lm(y ~ x1 + x2 + factor(id) + factor(time), data=d, weights=weight)
plm_call <- plm::plm(y ~ x1 + x2, data=d, index=c("id","time"), model="within", effect="twoways", weights=d$weight)
result <- data.frame(term=c("x1","x2"), weighted_dummy=coef(weighted_dummy)[c("x1","x2")], plm_backend=coef(plm_call)[c("x1","x2")])
write.csv(result,args[2],row.names=FALSE)
cat("plm reference version:",as.character(packageVersion("plm")),"\\n")
'''
    (OUT/'verify_r_backend.R').write_text(r_source)
    completed=subprocess.run(['Rscript',str(OUT/'verify_r_backend.R'),str(OUT/'synthetic_panel.csv'),str(OUT/'r_reference_coefficients.csv')],check=True,text=True,capture_output=True)
    print(completed.stdout.strip())
    reference=pd.read_csv(OUT/'r_reference_coefficients.csv')
    local=fit(values,weights); compatibility=fit(values,weights,compatible=True)
    assert np.allclose(local,reference.weighted_dummy,atol=1e-11,rtol=1e-11)
    assert np.allclose(compatibility,reference.plm_backend,atol=1e-11,rtol=1e-11)
    equal=fit(values,np.ones(n)); equal_compat=fit(values,np.ones(n),compatible=True)
    assert np.allclose(equal,equal_compat,atol=1e-12)

    # Weighted centered cross-products provide a scalable equivalent estimator.
    md=values-values.mean(axis=1,keepdims=True)
    xx=md[:,:,1:]; yy=md[:,:,0]
    mu=np.einsum('i,itp->tp',weights,md)/weights.sum()
    a=np.einsum('i,itp,itq->pq',weights,xx,xx)-weights.sum()*mu[:,1:].T@mu[:,1:]
    b=np.einsum('i,itp,it->p',weights,xx,yy)-weights.sum()*mu[:,1:].T@mu[:,0]
    moment=np.linalg.solve(a,b)
    assert np.allclose(moment,local,atol=1e-12)
    z=weighted_within(values,weights)
    assert np.allclose(z.mean(axis=1),0,atol=1e-12)
    assert np.allclose(np.einsum('i,itp->tp',weights,z),0,atol=1e-12)
    assert np.allclose(fit(values*1+0,weights*7),local,atol=1e-12)
    keep=weights>0
    assert np.allclose(fit(values[keep],weights[keep]),local,atol=1e-12)
    report=dict(status='passed',synthetic_only=True,seed=20261009,meshes=n,periods=t,
        r_reference=completed.stdout.strip(),python_weighted_twoways=local.tolist(),
        r_weighted_dummy=reference.weighted_dummy.tolist(),python_plm_compatibility=compatibility.tolist(),
        r_plm_backend=reference.plm_backend.tolist(),
        weighted_dummy_max_difference=float(np.max(abs(local-reference.weighted_dummy))),
        compatibility_max_difference=float(np.max(abs(compatibility-reference.plm_backend))),
        weighted_vs_compatibility_max_difference=float(np.max(abs(local-compatibility))),
        equal_weights_equivalence=True,weight_scale_invariance=True,zero_weight_exclusion_invariance=True,
        weighted_fixed_effect_orthogonality=True,weighted_moment_equivalence=True,
        downloaded_package_code_executed=False,empirical_gwpr_estimated=False,
        dense_national_distance_matrix_gb=134830**2*8/1e9)
    (OUT/'design_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
