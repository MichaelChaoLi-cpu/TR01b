"""Local weighted two-way FE on a balanced panel with a fixed-distance kernel.

The objective is weighted mesh/time dummy-equivalent WLS, not the tested
plm backend's unweighted within transform followed by weights. Uses existing
NumPy only; a sorted-latitude spherical-cap index avoids dense distances.
"""
from dataclasses import dataclass

import numpy as np

EARTH_RADIUS_KM = 6371.0088
SCALED_GRAM_MIN_EIGENVALUE = 1e-12


def mesh_centroids(codes):
    assert all(len(c)==8 and c.isdigit() and int(c[4])<8 and int(c[5])<8 for c in codes)
    latitude=np.array([int(c[:2])*2/3+int(c[4])/12+int(c[6])/120+1/240 for c in codes])
    longitude=np.array([int(c[2:4])+100+int(c[5])/8+int(c[7])/80+1/160 for c in codes])
    return np.column_stack([latitude,longitude])


def great_circle_km(center, coordinates):
    lat,lon=np.deg2rad(coordinates).T
    lat0,lon0=np.deg2rad(center)
    a=np.sin((lat-lat0)/2)**2+np.cos(lat)*np.cos(lat0)*np.sin((lon-lon0)/2)**2
    a=np.clip(a,0,1)
    return EARTH_RADIUS_KM*2*np.arctan2(np.sqrt(a),np.sqrt(1-a))


class RadiusIndex:
    """Exact great-circle radius queries after conservative cap bounds."""
    def __init__(self,coordinates):
        self.coordinates=np.asarray(coordinates,dtype=float)
        self.radians=np.deg2rad(self.coordinates)
        self.order=np.argsort(self.radians[:,0],kind='stable')
        self.sorted_latitude=self.radians[self.order,0]

    def query(self,center,radius_km,exclude=None):
        assert np.isfinite(radius_km) and radius_km>0
        lat0,lon0=np.deg2rad(center)
        angle=min(radius_km/EARTH_RADIUS_KM,np.pi)
        lo=np.searchsorted(self.sorted_latitude,lat0-angle,side='left')
        hi=np.searchsorted(self.sorted_latitude,lat0+angle,side='right')
        ids=self.order[lo:hi]
        if abs(lat0)+angle<np.pi/2 and angle<np.pi/2:
            lon_span=np.arcsin(min(1,np.sin(angle)/np.cos(lat0)))
            delta=(self.radians[ids,1]-lon0+np.pi)%(2*np.pi)-np.pi
            ids=ids[abs(delta)<=lon_span+1e-14]
        if exclude is not None:
            ids=ids[ids!=exclude]
        distance=great_circle_km(center,self.coordinates[ids])
        inside=distance<radius_km
        ids,distance=ids[inside],distance[inside]
        order=np.argsort(ids,kind='stable')
        return ids[order],distance[order]


def bisquare_weights(distance,radius_km):
    d=np.asarray(distance,dtype=float)
    assert radius_km>0 and np.all(d>=0)
    return np.where(d<radius_km,(1-(d/radius_km)**2)**2,0)


@dataclass
class LocalFit:
    status:str
    reason:str
    beta:np.ndarray
    time_effect:np.ndarray
    positive_meshes:int
    effective_meshes:float
    rank:int
    scaled_design_condition:float
    weighted_within_r2:float


class PanelMoments:
    def __init__(self,values):
        values=np.asarray(values,dtype=float)
        assert values.ndim==3 and values.shape[2]==3 and np.isfinite(values).all()
        self.values=values
        self.n,self.t,_=values.shape
        self.means=values.mean(axis=1)
        self.md=values-self.means[:,None,:]
        y,x1,x2=self.md.transpose(2,0,1)
        self.moments=np.column_stack([(x1*x1).sum(axis=1),(x1*x2).sum(axis=1),
            (x2*x2).sum(axis=1),(x1*y).sum(axis=1),(x2*y).sum(axis=1),(y*y).sum(axis=1)])
        self.features=np.column_stack([self.moments,self.md.reshape(self.n,self.t*3)])

    def fit(self,ids,weights):
        ids=np.asarray(ids,dtype=np.int64); weights=np.asarray(weights,dtype=float)
        assert len(ids)==len(weights) and np.all(weights>=0) and np.isfinite(weights).all()
        keep=weights>0; ids,weights=ids[keep],weights[keep]
        q=len(ids); sw=weights.sum()
        neff=float(sw*sw/(weights@weights)) if sw>0 else 0.
        def fail(reason,rank=0,condition=np.nan):
            return LocalFit('failed',reason,np.full(2,np.nan),np.full(self.t,np.nan),q,neff,rank,float(condition),np.nan)
        if q<2: return fail('fewer_than_two_positive_weight_training_meshes')
        # Exact weighted moments after removing local weighted period means.
        sums=weights@self.features[ids]
        mu=sums[6:].reshape(self.t,3)/sw
        a=np.array([[sums[0],sums[1]],[sums[1],sums[2]]])-sw*mu[:,1:].T@mu[:,1:]
        b=sums[3:5]-sw*mu[:,1:].T@mu[:,0]
        diag=np.diag(a)
        if not np.all(diag>0): return fail('zero_or_nonpositive_absorbed_regressor_information')
        scale=np.sqrt(diag)
        gram=a/scale[:,None]/scale[None,:]
        eigen=np.linalg.eigvalsh(gram)
        rank=int(np.count_nonzero(eigen>SCALED_GRAM_MIN_EIGENVALUE))
        if rank<2: return fail('rank_deficient_or_numerically_singular_absorbed_design',rank)
        condition=float(np.sqrt(eigen.max()/eigen.min()))
        beta=np.linalg.solve(gram,b/scale)/scale
        period=mu[:,0]-mu[:,1:]@beta
        assert np.allclose(period.mean(),0,atol=1e-9)
        sst=float(sums[5]-sw*(mu[:,0]@mu[:,0]))
        r2=float(beta@b/sst) if sst>0 else np.nan
        return LocalFit('ok','',beta,period,q,neff,rank,condition,r2)

    def qr_reference(self,ids,weights):
        md=self.md[ids]
        mu=np.einsum('i,itp->tp',weights,md)/weights.sum()
        z=md-mu[None,:,:]
        x=z[:,:,1:].reshape(-1,2); y=z[:,:,0].reshape(-1)
        root=np.repeat(np.sqrt(weights),self.t)
        beta=np.linalg.lstsq(x*root[:,None],y*root,rcond=None)[0]
        return beta,mu[:,0]-mu[:,1:]@beta

    def within_residual(self,focus,fit):
        assert fit.status=='ok'
        return self.md[focus,:,0]-self.md[focus,:,1:]@fit.beta-fit.time_effect


def result_row(code,coordinate,radius,fit):
    return {'Mesh Code':code,'Latitude':float(coordinate[0]),'Longitude':float(coordinate[1]),
        'Bandwidth km':float(radius),'Road Density Coefficient':float(fit.beta[0]),
        'Population Coefficient':float(fit.beta[1]),'Positive Weight Meshes':fit.positive_meshes,
        'Effective Weight Meshes':fit.effective_meshes,'Absorbed Rank':fit.rank,
        'Scaled Design Condition':fit.scaled_design_condition,
        'Weighted Within R Squared':fit.weighted_within_r2,'Fit Status':fit.status,'Failure Reason':fit.reason}
