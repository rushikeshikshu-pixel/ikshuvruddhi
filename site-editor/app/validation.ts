import { z } from "zod";
export const date=z.string().regex(/^\d{4}-\d{2}-\d{2}$/).refine(v=>!isNaN(Date.parse(v))&&new Date(v).toISOString().slice(0,10)===v,"Invalid date");
export const optionalDate=date.nullable().optional();
export const label=z.string().trim().min(1).max(120);
export const plotInput=z.object({plotNo:label,village:label,variety:label,caneType:z.enum(['Suru','Khodwa','Adsali','Other']),area:z.number().positive().max(10000),plantingDate:date,acquisitionDate:optionalDate,cloud:z.number().min(0).max(100).nullable().optional(),ndvi:z.number().min(-1).max(1).nullable().optional(),harvestDate:optionalDate,priority:z.enum(['Review','Ready','Hold']).default('Review')}).refine(v=>!v.acquisitionDate||v.acquisitionDate>=v.plantingDate,'Acquisition must follow planting').refine(v=>!v.harvestDate||v.harvestDate>=v.plantingDate,'Harvest must follow planting');
export const sampleInput=z.object({plotId:label,sampleDate:date,pol:z.number().min(0).max(40),brix:z.number().min(0).max(40),recovery:z.number().min(0).max(30).nullable().optional()}).refine(v=>v.pol<=v.brix,'Pol must not exceed Brix');
