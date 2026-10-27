INSERT INTO mills (owner_id,name,location,season) VALUES ('qa_other_owner','Other QA Mill','Local test','2026-27');
INSERT INTO plots (id,owner_id,plot_no,village,variety,cane_type,area,planting_date,priority,created_at) VALUES ('other-owner-plot','qa_other_owner','OTHER-001','Other cluster','CO-265','Suru',2,'2025-11-01','Hold','2026-10-01');
INSERT INTO samples (id,owner_id,plot_id,sample_date,pol,brix,created_at) VALUES ('other-owner-sample','qa_other_owner','other-owner-plot','2026-10-05',13,16,'2026-10-05');
