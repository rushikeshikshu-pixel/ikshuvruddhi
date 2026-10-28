export type Mill = {name:string;location:string;season:string};
export type Plot = {id:string;plotNo:string;village:string;variety:string;caneType:string;area:number;plantingDate:string;acquisitionDate:string|null;cloud:number|null;ndvi:number|null;harvestDate:string|null;priority:string;createdAt:string};
export type Sample = {id:string;plotId:string;sampleDate:string;pol:number;brix:number;recovery:number|null;createdAt:string};
export type Workspace = {mill:Mill|null;plots:Plot[];samples:Sample[]};
